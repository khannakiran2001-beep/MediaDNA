"""Application configuration.

All external integrations (Backblaze B2, Hugging Face) are optional. When
credentials are absent the app transparently falls back to local, deterministic
implementations so the MVP always runs.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

import tempfile

BASE_DIR = Path(__file__).resolve().parent.parent


def _writable_data_dir() -> Path:
    """Prefer the repo data dir; fall back to a temp dir on read-only hosts
    (e.g. serverless/Vercel where only /tmp is writable)."""
    candidate = BASE_DIR / "data"
    try:
        (candidate / "storage").mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        tmp = Path(tempfile.gettempdir()) / "mediadna"
        (tmp / "storage").mkdir(parents=True, exist_ok=True)
        return tmp


DATA_DIR = _writable_data_dir()
STORAGE_DIR = DATA_DIR / "storage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    app_name: str = "MediaDNA"
    database_url: str = f"sqlite:///{(DATA_DIR / 'mediadna.db').as_posix()}"

    # Hugging Face (optional) -----------------------------------------------
    hf_token: str = ""
    hf_caption_model: str = "Salesforce/blip-image-captioning-large"
    hf_detection_model: str = "facebook/detr-resnet-50"
    hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Backblaze B2 (optional) -----------------------------------------------
    b2_key_id: str = ""
    b2_app_key: str = ""
    b2_bucket_name: str = ""
    b2_bucket_id: str = ""
    b2_region: str = ""  # e.g. us-east-005; auto-resolved from B2 if blank

    embedding_dim: int = 384

    # Auth ------------------------------------------------------------------
    secret_key: str = "change-me-in-production-please"
    otp_ttl_seconds: int = 600          # 10 minutes
    otp_cooldown_seconds: int = 30      # min gap between code requests per email
    otp_max_per_hour: int = 8           # max code requests per email per hour
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    admin_emails: str = ""              # comma-separated; else first user is admin

    # Default admin account (email + password), created on startup if missing.
    default_admin_email: str = "admin@mediadna.app"
    default_admin_password: str = "MediaDNA!Admin2026"
    default_admin_name: str = "Administrator"

    # SMTP (optional). Without these, OTPs run in dev mode (surfaced in-app).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "MediaDNA <no-reply@mediadna.local>"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    # Free text-to-image backend (no API key required) ----------------------
    pollinations_enabled: bool = True
    pollinations_model: str = "flux"
    gen_width: int = 768
    gen_height: int = 512
    # Verify TLS certs on outbound calls. Auto-retry insecurely if the network
    # (SSL inspection / missing CA) breaks verification — controlled here.
    ssl_verify: bool = True

    @property
    def huggingface_enabled(self) -> bool:
        return bool(self.hf_token)

    @property
    def b2_enabled(self) -> bool:
        return bool(self.b2_key_id and self.b2_app_key and self.b2_bucket_name)


@lru_cache
def get_settings() -> Settings:
    return Settings()
