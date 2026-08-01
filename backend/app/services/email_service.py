"""Email delivery.

Sends via SMTP when configured; otherwise runs in **dev mode** — the message is
logged and the caller surfaces the OTP in-app so the flow is testable without a
mail server.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

logger = logging.getLogger("mediadna.email")


def send_email(to: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not settings.smtp_configured:
        logger.info("[DEV EMAIL] to=%s subject=%s\n%s", to, subject, body)
        return False  # not actually sent
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("SMTP send failed: %s", exc)
        return False


def send_otp(to: str, code: str, purpose: str) -> bool:
    action = "Complete your registration" if purpose == "register" else "Sign in"
    body = (
        f"Your MediaDNA verification code is: {code}\n\n"
        f"{action} by entering this code. It expires in 10 minutes.\n"
        "If you didn't request this, you can ignore this email."
    )
    return send_email(to, "Your MediaDNA verification code", body)
