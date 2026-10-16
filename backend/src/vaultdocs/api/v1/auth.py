"""
Authentication API endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterResponse,
    RegisterUserRequest,
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
    login_user,
    register_user,
    request_password_reset,
    resend_user_otp,
    reset_user_password,
    update_user_profile,
    verify_password_reset_token,
    verify_user_otp,
)
from vaultdocs.services.email import EmailDeliveryError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vaultdocs.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


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
    response_model=TokenResponse,
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user and return a JWT access token.
    """
    try:
        return await login_user(
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
