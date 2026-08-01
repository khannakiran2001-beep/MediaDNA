"""ORM models — the DNA record and its relationships."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    """A single AI-generated (or uploaded) media asset with its full DNA."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(32), default="pending")  # image | video | audio | document
    mime_type: Mapped[str] = mapped_column(String(128), default="")

    # Provenance -------------------------------------------------------------
    prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    provider: Mapped[str] = mapped_column(String(64), default="")
    generation_params: Mapped[dict] = mapped_column(JSON, default=dict)

    # Organisation -----------------------------------------------------------
    project: Mapped[str] = mapped_column(String(128), default="")
    campaign: Mapped[str] = mapped_column(String(128), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)

    # AI analysis ------------------------------------------------------------
    caption: Mapped[str] = mapped_column(Text, default="")
    objects_detected: Mapped[list] = mapped_column(JSON, default=list)
    people_detected: Mapped[int] = mapped_column(Integer, default=0)
    brand_logos: Mapped[list] = mapped_column(JSON, default=list)
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    dominant_colors: Mapped[list] = mapped_column(JSON, default=list)
    visual_style: Mapped[str] = mapped_column(String(128), default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    safety: Mapped[dict] = mapped_column(JSON, default=dict)

    # Search / dedup ---------------------------------------------------------
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    checksum: Mapped[str] = mapped_column(String(64), default="", index=True)

    # Storage ----------------------------------------------------------------
    storage_key: Mapped[str] = mapped_column(String(512), default="")
    storage_backend: Mapped[str] = mapped_column(String(32), default="local")
    thumbnail_key: Mapped[str] = mapped_column(String(512), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)

    # Version control --------------------------------------------------------
    version: Mapped[int] = mapped_column(Integer, default=1)
    root_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)

    approval_status: Mapped[str] = mapped_column(String(32), default="pending")
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_email: Mapped[str] = mapped_column(String(255), default="")
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    parent = relationship("Asset", remote_side=[id], backref="children")
    comments = relationship("Comment", back_populates="asset", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="asset", cascade="all, delete-orphan")

    edges_out = relationship(
        "Relationship",
        foreign_keys="Relationship.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class Relationship(Base):
    """A typed, directed edge in the lineage graph."""

    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    kind: Mapped[str] = mapped_column(String(48))  # created_from | edited_to | upscaled | duplicate_of | used_in
    score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source = relationship("Asset", foreign_keys=[source_id], back_populates="edges_out")
    target = relationship("Asset", foreign_keys=[target_id])


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    author: Mapped[str] = mapped_column(String(128), default="anonymous")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    asset = relationship("Asset", back_populates="comments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    asset = relationship("Asset", back_populates="audit_logs")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(255), default="")  # pbkdf2; empty = OTP-only
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(default=True)
    verified: Mapped[bool] = mapped_column(default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(16), default="login")  # login | register
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user = relationship("User")


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(32), default="collection")  # collection | campaign | project | smart
    rule: Mapped[dict] = mapped_column(JSON, default=dict)  # for smart collections
    asset_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
