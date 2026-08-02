"""Email delivery.

Sends via SMTP when configured (STARTTLS on 587, implicit SSL on 465);
otherwise runs in **dev mode** — the message is logged and the caller surfaces
the OTP in-app so the flow is testable without a mail server.

``send_email`` / ``send_otp`` return ``(sent: bool, error: str | None)`` so the
caller can tell the difference between "dev mode" and "configured but failed".
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from ..config import get_settings

logger = logging.getLogger("mediadna.email")


def send_email(to: str, subject: str, body: str) -> tuple[bool, str | None]:
    settings = get_settings()
    if not settings.smtp_configured:
        logger.info("[DEV EMAIL] to=%s subject=%s\n%s", to, subject, body)
        return False, None  # not sent — dev mode

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if settings.smtp_port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=25, context=ctx) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        logger.info("OTP email sent to %s", to)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed — check SMTP_USER / SMTP_PASSWORD (Gmail needs an App Password)."
    except Exception as exc:  # pragma: no cover
        logger.error("SMTP send failed: %s", exc)
        return False, f"{type(exc).__name__}: {exc}"


def send_otp(to: str, code: str, purpose: str) -> tuple[bool, str | None]:
    action = "Complete your registration" if purpose == "register" else "Sign in"
    body = (
        f"Your MediaDNA verification code is: {code}\n\n"
        f"{action} by entering this code. It expires in 10 minutes.\n"
        "If you didn't request this, you can ignore this email."
    )
    return send_email(to, "Your MediaDNA verification code", body)
