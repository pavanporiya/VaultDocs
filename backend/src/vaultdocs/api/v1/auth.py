"""
Authentication API endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.core.rate_limit import RateLimitError, rate_limiter
from vaultdocs.core.security import create_access_token, sha256_hex
from vaultdocs.core.settings import settings
from vaultdocs.db.session import get_db
from vaultdocs.models.login_challenge import LoginChallenge
from vaultdocs.schemas.auth import (
    ApprovalRequiredResponse,
    ChallengeActionResponse,
    CompleteChallengeRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterResponse,
    RegisterUserRequest,
    ResendChallengeResponse,
    ResendOtpRequest,
    ResendOtpResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
    VerifyResetTokenRequest,
    VerifyResetTokenResponse,
)
from vaultdocs.schemas.user import UserUpdate  # noqa: TC001
from vaultdocs.services.auth import (
    UnverifiedUserError,
    authenticate_user,
    register_user,
    request_password_reset,
    resend_user_otp,
    reset_user_password,
    update_user_profile,
    verify_password_reset_token,
    verify_user_otp,
)
from vaultdocs.services.device_approval import (
    DEVICE_COOKIE_NAME,
    ChallengeNotFoundError,
    ChallengeStateError,
    cancel_challenge,
    complete_login_challenge,
    create_login_challenge,
    create_trusted_device,
    get_valid_trusted_device,
    is_https_request,
    resend_login_challenge,
    set_device_cookie,
    touch_trusted_device,
)
from vaultdocs.services.email import EmailDeliveryError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vaultdocs.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def _client_ip(request: Request) -> str | None:
    """Best-effort client IP for rate limiting and audit records."""
    if request.client and request.client.host:
        return request.client.host
    return None


def _enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Apply an auth rate limit, mapping violations to HTTP 429."""
    try:
        rate_limiter.check(key, limit, window_seconds)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: RegisterUserRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Register a new user and dispatch a verification OTP to the registered email.

    The user remains unverified until the OTP is successfully validated.
    """
    try:
        user = await register_user(
            db=db,
            user_data=user_data,
        )

        return RegisterResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            message="Verification code sent to your email. Please verify your account.",
        )

    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Unable to send verification email. "
                "Please verify email server configuration and try again."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_otp(
    request_data: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyOtpResponse:
    """
    Validate the single-use OTP code and activate the user account.
    """
    try:
        user, token = await verify_user_otp(
            db=db,
            email=request_data.email,
            otp_code=request_data.otp,
        )

        return VerifyOtpResponse(
            message="Account successfully verified.",
            access_token=token,
            token_type="bearer",  # noqa: S106
            user=UserResponse.model_validate(user),
        )

    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Unable to send verification email. "
                "Please verify email server configuration and try again."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/resend-otp",
    response_model=ResendOtpResponse,
    status_code=status.HTTP_200_OK,
)
async def resend_otp(
    request_data: ResendOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> ResendOtpResponse:
    """
    Resend an OTP verification code, invalidating previous codes and enforcing cooldowns.
    """
    try:
        cooldown = await resend_user_otp(
            db=db,
            email=request_data.email,
        )

        return ResendOtpResponse(
            message="A new verification code has been sent to your email.",
            email=request_data.email,
            resend_cooldown_seconds=cooldown,
        )

    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to send verification email. Please try again later.",
        ) from exc
    except ValueError as exc:
        msg = str(exc)
        status_code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if "wait" in msg.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=msg,
        ) from exc


@router.post(
    "/login",
    response_model=None,
)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse | JSONResponse:
    """
    Authenticate a user with email and password.

    Returns a JWT immediately only when the request arrives from a trusted
    device whose trust has not expired or been revoked. Otherwise returns
    HTTP 202 with a short-lived, single-use approval challenge: no JWT is
    issued until the sign-in is approved with the email approval code (OTP).
    """
    client_ip = _client_ip(request)
    normalized_email = login_data.email.strip().lower()

    _enforce_rate_limit(
        f"login:email:{normalized_email}",
        settings.rate_limit_login_attempts,
        settings.rate_limit_login_window_seconds,
    )
    _enforce_rate_limit(
        f"login:ip:{client_ip or 'unknown'}",
        settings.rate_limit_login_attempts,
        settings.rate_limit_login_window_seconds,
    )

    try:
        user = await authenticate_user(
            db=db,
            login_data=login_data,
        )
    except UnverifiedUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": str(exc),
                "needs_verification": True,
                "email": exc.email,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    device_cookie = request.cookies.get(DEVICE_COOKIE_NAME)
    trusted_device = await get_valid_trusted_device(db, user.id, device_cookie)

    if trusted_device is not None:
        await touch_trusted_device(
            db,
            trusted_device,
            remember_device=login_data.remember_device,
        )
        access_token = create_access_token(subject=user.email)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",  # noqa: S106
            device_remembered=True,
        )

    # Untrusted (or stale) device: require explicit approval. Approval never
    # happens automatically, and any presented stale cookie is cleared.
    _enforce_rate_limit(
        f"challenge:{normalized_email}",
        settings.rate_limit_challenge_attempts,
        settings.rate_limit_login_window_seconds,
    )

    try:
        challenge = await create_login_challenge(
            db,
            user,
            remember_device=login_data.remember_device,
            device_id_hash=sha256_hex(device_cookie) if device_cookie else None,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Unable to send sign-in approval. Please verify email server "
                "configuration and try again."
            ),
        ) from exc

    approval = ApprovalRequiredResponse(
        challenge_id=challenge.challenge_id,
        delivery="email",
        message="Approve this sign-in with the code we emailed you.",
        expires_in_seconds=settings.login_challenge_expire_seconds,
        resend_cooldown_seconds=settings.login_approval_code_cooldown_seconds,
    )

    payload = JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=approval.model_dump(),
    )
    if device_cookie:
        payload.delete_cookie(key=DEVICE_COOKIE_NAME, path="/")
    return payload


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """
    Request a password reset link for the provided email address.

    Always returns a generic success message to prevent user enumeration,
    while enforcing rate-limiting cooldowns per email address.
    """
    try:
        await request_password_reset(
            db=db,
            email=request_data.email,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to send password reset email. Please try again later.",
        ) from exc
    except ValueError as exc:
        msg = str(exc)
        if "wait" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=msg,
            ) from exc
        # Suppress other user enumeration hints
        pass

    return ForgotPasswordResponse(
        message=(
            "If your email is registered, you will receive password reset instructions shortly."
        ),
    )


@router.post(
    "/verify-reset-token",
    response_model=VerifyResetTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_reset_token(
    request_data: VerifyResetTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyResetTokenResponse:
    """
    Check if a password reset token is valid and not expired or already used.
    """
    try:
        user = await verify_password_reset_token(
            db=db,
            token=request_data.token,
            email=request_data.email,
        )
        return VerifyResetTokenResponse(
            valid=True,
            email=user.email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """
    Reset user password using a valid, single-use password reset token.
    """
    try:
        await reset_user_password(
            db=db,
            token=request_data.token,
            new_password=request_data.new_password,
            email=request_data.email,
        )
        return ResetPasswordResponse(
            message=(
                "Password has been successfully reset. You can now sign in with your new password."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Return the currently authenticated user.
    """
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
)
async def update_me(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update the currently authenticated user's profile (full_name).
    """
    try:
        updated_user = await update_user_profile(
            db=db,
            user=current_user,
            update_data=update_data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return UserResponse.model_validate(updated_user)


# ---------------------------------------------------------------------------
# Sign-in approval challenge endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/login/challenges/{challenge_id}/complete",
    response_model=TokenResponse,
)
async def complete_login_challenge_endpoint(
    challenge_id: str,
    request_data: CompleteChallengeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Finish an approved sign-in and receive the JWT.

    The challenge is consumed atomically and can never be replayed. When the
    user asked to be remembered, a 30-day trusted-device cookie is issued
    together with the token. Denied, cancelled, expired and unknown
    challenges are always blocked.
    """
    client_ip = _client_ip(request)
    _enforce_rate_limit(
        f"complete:{challenge_id}",
        settings.rate_limit_poll_attempts,
        settings.rate_limit_poll_window_seconds,
    )

    try:
        user, challenge = await complete_login_challenge(
            db,
            challenge_id,
            approval_code=request_data.approval_code,
            remember_device=request_data.remember_device,
        )
    except ChallengeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sign-in request not found.",
        ) from exc
    except ChallengeStateError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    access_token = create_access_token(subject=user.email)

    device_remembered = False
    if challenge.remember_device:
        _device, raw_device_token = await create_trusted_device(
            db,
            user.id,
            device_name=request_data.device_name,
            user_agent=request.headers.get("user-agent"),
            ip_address=client_ip,
        )
        set_device_cookie(
            response,
            raw_device_token,
            https=is_https_request(
                scheme=request.url.scheme,
                forwarded_proto=request.headers.get("x-forwarded-proto"),
            ),
        )
        device_remembered = True

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # noqa: S106
        device_remembered=device_remembered,
    )


@router.post(
    "/login/challenges/{challenge_id}/resend",
    response_model=ResendChallengeResponse,
)
async def resend_login_challenge_endpoint(
    challenge_id: str,
    db: AsyncSession = Depends(get_db),
) -> ResendChallengeResponse:
    """
    Re-dispatch a fresh email approval code for a pending
    challenge. Enforces cooldowns and rate limits.
    """
    _enforce_rate_limit(
        f"resend:{challenge_id}",
        settings.rate_limit_resend_attempts,
        settings.rate_limit_resend_window_seconds,
    )

    try:
        await resend_login_challenge(db, challenge_id)
    except ChallengeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sign-in request not found.",
        ) from exc
    except ChallengeStateError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to send sign-in approval. Please try again later.",
        ) from exc

    return ResendChallengeResponse(
        message="A new sign-in approval code was emailed to you.",
        delivery="email",
        resend_cooldown_seconds=settings.login_approval_code_cooldown_seconds,
    )


@router.post(
    "/login/challenges/{challenge_id}/cancel",
    response_model=ChallengeActionResponse,
)
async def cancel_login_challenge(
    challenge_id: str,
    db: AsyncSession = Depends(get_db),
) -> ChallengeActionResponse:
    """
    Cancel a pending sign-in challenge from the waiting client itself.
    Cancellation blocks the login.
    """
    _enforce_rate_limit(
        f"cancel:{challenge_id}",
        settings.rate_limit_poll_attempts,
        settings.rate_limit_poll_window_seconds,
    )

    try:
        await cancel_challenge(db, challenge_id)
    except ChallengeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sign-in request not found.",
        ) from exc
    except ChallengeStateError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return ChallengeActionResponse(
        status=LoginChallenge.STATUS_CANCELLED,
        message="Sign-in request cancelled.",
    )
