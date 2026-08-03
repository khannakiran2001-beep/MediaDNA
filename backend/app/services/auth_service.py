"""Authentication service — email OTP register/login + sessions."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from email_validator import (
    EmailNotValidError,
    EmailSyntaxError,
    EmailUndeliverableError,
    validate_email,
)
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from ..models import OtpCode, Session, User
from . import email_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2$200000${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return secrets.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def _aware(dt: datetime) -> datetime:
    """SQLite may hand back naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: DbSession) -> None:
        self.db = db
        self.settings = get_settings()

    # -- validation ---------------------------------------------------------
    def _validate_email(self, email: str) -> str:
        """Validate syntax and (best-effort) deliverability. Returns normalized email."""
        email = (email or "").strip()
        try:
            return validate_email(email, check_deliverability=True).normalized.lower()
        except EmailSyntaxError as exc:
            raise AuthError(f"Invalid email address: {exc}")
        except EmailUndeliverableError as exc:
            msg = str(exc).lower()
            if "does not exist" in msg or "does not accept email" in msg or "no mx" in msg:
                raise AuthError("That email domain can't receive mail — please check the address")
            # DNS/infra hiccup (not a bad domain) — accept if syntax is valid.
            try:
                return validate_email(email, check_deliverability=False).normalized.lower()
            except EmailNotValidError as exc2:
                raise AuthError(f"Invalid email address: {exc2}")

    def _enforce_otp_rate(self, email: str) -> None:
        """Cooldown between code requests + hourly cap, per email (anti-abuse)."""
        now = _now()
        recents = list(self.db.scalars(
            select(OtpCode).where(OtpCode.email == email).order_by(OtpCode.created_at.desc())
        ))
        if recents:
            age = (now - _aware(recents[0].created_at)).total_seconds()
            if age < self.settings.otp_cooldown_seconds:
                wait = int(self.settings.otp_cooldown_seconds - age) or 1
                raise AuthError(f"Please wait {wait}s before requesting another code")
            in_last_hour = sum(1 for o in recents if (now - _aware(o.created_at)).total_seconds() < 3600)
            if in_last_hour >= self.settings.otp_max_per_hour:
                raise AuthError("Too many code requests — please try again later")

    # -- users --------------------------------------------------------------
    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def _role_for(self, email: str) -> str:
        admins = self.settings.admin_email_set
        if email.lower() in admins:
            return "admin"
        # first user ever becomes admin when no ADMIN_EMAILS configured
        if not admins and self.db.scalar(select(User).limit(1)) is None:
            return "admin"
        return "user"

    # -- OTP request --------------------------------------------------------
    def request_otp(self, email: str, name: str = "", purpose: str = "login", password: str = "") -> dict:
        email = self._validate_email(email)

        user = self.get_by_email(email)
        if purpose == "register":
            if user and user.verified:
                raise AuthError("An account with this email already exists — sign in instead")
            if len(password) < 8:
                raise AuthError("Password must be at least 8 characters")
        if purpose == "login" and user is None:
            raise AuthError("No account found for this email — register first")

        self._enforce_otp_rate(email)

        if user is None:
            user = User(email=email, name=name.strip(), role=self._role_for(email))
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        elif name and not user.name:
            user.name = name.strip()
        # Set/refresh the password during registration (account stays unverified
        # until the emailed code is confirmed).
        if purpose == "register" and password:
            user.password_hash = hash_password(password)
        self.db.commit()

        code = f"{secrets.randbelow(1_000_000):06d}"
        otp = OtpCode(
            email=email,
            code_hash=_hash(code),
            purpose=purpose,
            expires_at=_now() + timedelta(seconds=self.settings.otp_ttl_seconds),
        )
        self.db.add(otp)
        self.db.commit()

        sent, error = email_service.send_otp(email, code, purpose)
        if self.settings.smtp_configured and not sent:
            # Configured but delivery failed — tell the user instead of failing silently.
            raise AuthError(error or "Could not send the verification email. Please try again.")
        result = {"email": email, "sent": sent, "dev_mode": not self.settings.smtp_configured}
        if not self.settings.smtp_configured:
            result["dev_otp"] = code  # surfaced in-app when no mailer is set up
        return result

    # -- OTP verify ---------------------------------------------------------
    def _consume_otp(self, email: str, code: str, purposes: set[str]) -> User:
        """Validate + consume the latest matching OTP; return the user."""
        email = email.strip().lower()
        otp = self.db.scalar(
            select(OtpCode)
            .where(
                OtpCode.email == email,
                OtpCode.consumed == False,  # noqa: E712
                OtpCode.purpose.in_(purposes),
            )
            .order_by(OtpCode.created_at.desc())
        )
        if otp is None:
            raise AuthError("Request a new code")
        if otp.attempts >= 5:
            raise AuthError("Too many attempts — request a new code")
        if _aware(otp.expires_at) < _now():
            raise AuthError("Code expired — request a new one")

        otp.attempts += 1
        self.db.commit()
        if otp.code_hash != _hash(code.strip()):
            raise AuthError("Incorrect code")

        otp.consumed = True
        user = self.get_by_email(email)
        if user is None:
            raise AuthError("Account not found")
        self.db.commit()
        return user

    def verify_otp(self, email: str, code: str) -> tuple[User, str]:
        user = self._consume_otp(email, code, {"login", "register"})
        user.verified = True
        user.last_login = _now()
        self.db.commit()
        return user, self._issue_token(user)

    # -- password reset -----------------------------------------------------
    def request_password_reset(self, email: str) -> dict:
        email = self._validate_email(email)
        user = self.get_by_email(email)
        if user is None:
            raise AuthError("No account found for this email")
        self._enforce_otp_rate(email)
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.db.add(OtpCode(
            email=email, code_hash=_hash(code), purpose="reset",
            expires_at=_now() + timedelta(seconds=self.settings.otp_ttl_seconds),
        ))
        self.db.commit()
        sent, error = email_service.send_otp(email, code, "reset")
        if self.settings.smtp_configured and not sent:
            raise AuthError(error or "Could not send the reset email. Please try again.")
        result = {"email": email, "sent": sent, "dev_mode": not self.settings.smtp_configured}
        if not self.settings.smtp_configured:
            result["dev_otp"] = code
        return result

    def reset_password(self, email: str, code: str, new_password: str) -> tuple[User, str]:
        if len(new_password) < 8:
            raise AuthError("Password must be at least 8 characters")
        user = self._consume_otp(email, code, {"reset"})
        user.password_hash = hash_password(new_password)
        user.verified = True
        user.last_login = _now()
        self.db.commit()
        return user, self._issue_token(user)

    # -- password login -----------------------------------------------------
    def login_password(self, email: str, password: str) -> tuple[User, str]:
        email = email.strip().lower()
        user = self.get_by_email(email)
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password")
        if not user.is_active:
            raise AuthError("Account is deactivated")
        if not user.verified:
            raise AuthError("Please verify your email first — enter the code we sent you")
        user.last_login = _now()
        self.db.commit()
        return user, self._issue_token(user)

    def _issue_token(self, user: User) -> str:
        token = secrets.token_urlsafe(32)
        self.db.add(Session(
            token=token,
            user_id=user.id,
            expires_at=_now() + timedelta(seconds=self.settings.session_ttl_seconds),
        ))
        self.db.commit()
        return token

    def ensure_default_admin(self) -> None:
        """Create the configured default admin (email + password) if absent."""
        email = self.settings.default_admin_email.strip().lower()
        if not email or not self.settings.default_admin_password:
            return
        user = self.get_by_email(email)
        if user is None:
            self.db.add(User(
                email=email,
                name=self.settings.default_admin_name,
                role="admin",
                verified=True,
                password_hash=hash_password(self.settings.default_admin_password),
            ))
            self.db.commit()
        elif not user.password_hash:
            user.password_hash = hash_password(self.settings.default_admin_password)
            user.role = "admin"
            self.db.commit()

    # -- sessions -----------------------------------------------------------
    def user_for_token(self, token: str) -> User | None:
        if not token:
            return None
        sess = self.db.get(Session, token)
        if sess is None or _aware(sess.expires_at) < _now():
            return None
        user = self.db.get(User, sess.user_id)
        return user if user and user.is_active else None

    def logout(self, token: str) -> None:
        sess = self.db.get(Session, token)
        if sess:
            self.db.delete(sess)
            self.db.commit()
