"""
Email delivery service for VaultDocs authentication.

Handles verification OTP delivery using SMTP (default Gmail STARTTLS).
Protects secrets: credentials and OTP codes are never logged or echoed in errors.
Provides isolated in-memory test hooks for automated test suites.
"""

from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from vaultdocs.core.settings import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when an email cannot be sent due to configuration or delivery issues."""


# In-memory outbox and control flags for automated test environments.
_test_outbox: list[dict[str, Any]] = []
_mock_smtp_mode: bool = False
_mock_smtp_fail: bool = False


def set_mock_smtp(enabled: bool, *, should_fail: bool = False) -> None:
    """
    Enable or disable mock SMTP mode for automated tests.

    When enabled, emails are placed in the test outbox without contacting
    any network server. If should_fail is True, EmailDeliveryError is raised.
    """
    global _mock_smtp_mode, _mock_smtp_fail
    _mock_smtp_mode = enabled
    _mock_smtp_fail = should_fail


def get_test_outbox() -> list[dict[str, Any]]:
    """Return delivered messages captured in test mode."""
    return list(_test_outbox)


def clear_test_outbox() -> None:
    """Clear captured test messages."""
    _test_outbox.clear()


def _build_html_body(safe_name: str, safe_otp: str, expire_min: int) -> str:
    """Build clean responsive HTML email body with lines under 99 characters."""
    css_body = (
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;"
        "background: #0b0f19; color: #f3f4f6; padding: 24px; margin: 0;"
    )
    css_card = (
        "max-width: 480px; margin: 0 auto; background: #111827; "
        "border: 1px solid #1f2937; border-radius: 12px; padding: 32px;"
    )
    css_badge = (
        "display: inline-block; padding: 4px 12px; "
        "background: rgba(99, 102, 241, 0.15); color: #818cf8; "
        "border-radius: 6px; font-weight: 600; font-size: 13px; margin-bottom: 16px;"
    )
    css_otp_box = (
        "background: #1f2937; border: 1px solid #374151; "
        "border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0;"
    )
    css_otp = (
        "font-family: monospace; font-size: 32px; "
        "font-weight: 800; letter-spacing: 8px; color: #6366f1;"
    )
    css_footer = (
        "font-size: 12px; color: #6b7280; margin-top: 24px; "
        "border-top: 1px solid #1f2937; padding-top: 16px;"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="{css_body}">
  <div style="{css_card}">
    <div style="{css_badge}">VaultDocs Security</div>
    <h1 style="font-size: 20px; font-weight: 700; color: #fff; margin: 0 0 8px;">
      Verify Your Email Address
    </h1>
    <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 8px 0;">
      Hello {safe_name},
    </p>
    <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 8px 0;">
      Please enter the verification code below to activate your account:
    </p>
    <div style="{css_otp_box}">
      <span style="{css_otp}">{safe_otp}</span>
    </div>
    <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 8px 0;">
      This code expires in <strong>{expire_min} minutes</strong>. Never share this code.
    </p>
    <div style="{css_footer}">
      <p style="margin: 0;">If you didn't request this code, you can safely ignore this email.</p>
    </div>
  </div>
</body>
</html>"""


def send_verification_email(
    to_email: str,
    recipient_name: str,
    otp_code: str,
) -> None:
    """
    Send an OTP verification email to the user.

    Raises EmailDeliveryError if SMTP is unconfigured or if transmission fails.
    Never logs credentials or plain text OTP codes.
    """
    if _mock_smtp_mode:
        if _mock_smtp_fail:
            raise EmailDeliveryError("Mock SMTP delivery failure for testing.")
        _test_outbox.append(
            {
                "to_email": to_email,
                "recipient_name": recipient_name,
                "otp_code": otp_code,
            }
        )
        return

    smtp_user = settings.smtp_username
    smtp_pass = settings.smtp_password

    if not smtp_user or not smtp_pass:
        raise EmailDeliveryError(
            "SMTP credentials not configured. Please set SMTP_USERNAME and SMTP_PASSWORD."
        )

    from_email = settings.smtp_from_email or smtp_user
    from_name = settings.smtp_from_name or "VaultDocs"

    msg = EmailMessage()
    msg["Subject"] = f"{otp_code} is your VaultDocs verification code"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    safe_name = html.escape(recipient_name or "User")
    safe_otp = html.escape(otp_code)
    expire_min = settings.otp_expire_minutes

    text_content = (
        f"Hello {recipient_name},\n\n"
        f"Your VaultDocs verification code is: {otp_code}\n\n"
        f"This code will expire in {expire_min} minutes.\n"
        f"If you did not request this code, please ignore this email.\n\n"
        f"— The VaultDocs Team"
    )

    html_content = _build_html_body(safe_name, safe_otp, expire_min)

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as exc:
        logger.error(
            "SMTP transmission failed: %s (%s)",
            type(exc).__name__,
            "connection/authentication error",
        )
        raise EmailDeliveryError(
            f"Failed to deliver verification email via SMTP ({type(exc).__name__})."
        ) from None


def _build_password_reset_html_body(
    safe_name: str,
    reset_url: str,
    safe_token: str,
    expire_min: int,
) -> str:
    """Build responsive HTML email body for password reset."""
    css_body = (
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;"
        "background: #0b0f19; color: #f3f4f6; padding: 24px; margin: 0;"
    )
    css_card = (
        "max-width: 480px; margin: 0 auto; background: #111827; "
        "border: 1px solid #1f2937; border-radius: 12px; padding: 32px;"
    )
    css_badge = (
        "display: inline-block; padding: 4px 12px; "
        "background: rgba(99, 102, 241, 0.15); color: #818cf8; "
        "border-radius: 6px; font-weight: 600; font-size: 13px; margin-bottom: 16px;"
    )
    css_btn = (
        "display: inline-block; background: #6366f1; color: #ffffff; "
        "text-decoration: none; padding: 12px 24px; border-radius: 8px; "
        "font-weight: 600; font-size: 14px; margin: 20px 0;"
    )
    css_badge_box = (
        "background: #1f2937; border: 2px solid #374151; "
        "border-radius: 10px; padding: 18px 24px; margin: 20px 0; "
        "text-align: center;"
    )
    css_badge_val = (
        "font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; "
        "font-size: 30px; font-weight: 800; letter-spacing: 8px; "
        "color: #818cf8; text-transform: uppercase;"
    )
    css_footer = (
        "font-size: 12px; color: #6b7280; margin-top: 24px; "
        "border-top: 1px solid #1f2937; padding-top: 16px;"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="{css_body}">
  <div style="{css_card}">
    <div style="{css_badge}">VaultDocs Security</div>
    <h1 style="font-size: 20px; font-weight: 700; color: #fff; margin: 0 0 8px;">
      Reset Your Password
    </h1>
    <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 8px 0;">
      Hello {safe_name},
    </p>
    <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 8px 0;">
      We received a request to reset your VaultDocs password.
      Click the button below to choose a new password:
    </p>
    <div style="text-align: center;">
      <a href="{reset_url}" style="{css_btn}">Reset Password</a>
    </div>
    <p style="font-size: 13px; line-height: 1.5; color: #9ca3af; margin: 8px 0;">
      Or enter this 6-character reset code directly into the reset form:
    </p>
    <div style="{css_badge_box}">
      <span style="{css_badge_val}">{safe_token}</span>
    </div>
    <p style="font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 8px 0;">
      This link and code will expire in <strong>{expire_min} minutes</strong>.
    </p>
    <div style="{css_footer}">
      <p style="margin: 0;">
        If you did not request a password reset, you can safely ignore this email.
        Your password will remain unchanged.
      </p>
    </div>
  </div>
</body>
</html>"""


def send_password_reset_email(
    to_email: str,
    recipient_name: str,
    reset_token: str,
) -> None:
    """
    Send a password reset email containing a time-limited reset link and token.

    Raises EmailDeliveryError if SMTP is unconfigured or transmission fails.
    Never logs credentials, passwords, or reset tokens.
    """
    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={reset_token}"

    if _mock_smtp_mode:
        if _mock_smtp_fail:
            raise EmailDeliveryError("Mock SMTP delivery failure for testing.")
        _test_outbox.append(
            {
                "to_email": to_email,
                "recipient_name": recipient_name,
                "reset_token": reset_token,
                "reset_url": reset_url,
                "type": "password_reset",
            }
        )
        return

    smtp_user = settings.smtp_username
    smtp_pass = settings.smtp_password

    if not smtp_user or not smtp_pass:
        raise EmailDeliveryError(
            "SMTP credentials not configured. Please set SMTP_USERNAME and SMTP_PASSWORD."
        )

    from_email = settings.smtp_from_email or smtp_user
    from_name = settings.smtp_from_name or "VaultDocs"

    msg = EmailMessage()
    msg["Subject"] = "Reset your VaultDocs password"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    safe_name = html.escape(recipient_name or "User")
    safe_token = html.escape(reset_token)
    expire_min = settings.password_reset_expire_minutes

    text_content = (
        f"Hello {recipient_name},\n\n"
        f"We received a request to reset your VaultDocs password.\n"
        f"Reset Link: {reset_url}\n\n"
        f"Reset Code: {reset_token}\n\n"
        f"This link and code will expire in {expire_min} minutes.\n"
        f"If you did not request a password reset, you can safely ignore this email.\n\n"
        f"— The VaultDocs Team"
    )

    html_content = _build_password_reset_html_body(
        safe_name=safe_name,
        reset_url=reset_url,
        safe_token=safe_token,
        expire_min=expire_min,
    )

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as exc:
        logger.error(
            "SMTP password reset transmission failed: %s",
            type(exc).__name__,
        )
        raise EmailDeliveryError(
            f"Failed to deliver password reset email via SMTP ({type(exc).__name__})."
        ) from None
