"""Pydantic schemas for API I/O."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    media_type: str
    caption: str
    model: str
    provider: str
    project: str
    campaign: str
    tags: list[str]
    visual_style: str
    quality_score: float
    approval_status: str
    owner_email: str
    version: int
    root_id: str
    parent_id: str | None
    thumbnail_key: str
    dominant_colors: list[str]
    created_at: datetime


class AssetDetail(AssetSummary):
    prompt: str
    negative_prompt: str
    generation_params: dict[str, Any]
    objects_detected: list[Any]
    people_detected: int
    brand_logos: list[Any]
    ocr_text: str
    safety: dict[str, Any]
    checksum: str
    storage_key: str
    storage_backend: str
    size_bytes: int
    width: int
    height: int
    downloads: int
    provenance: dict[str, Any]


class CommentIn(BaseModel):
    author: str = "anonymous"
    body: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    author: str
    body: str
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = ""
    provider: str | None = None
    model: str | None = None
    project: str | None = None
    tag: str | None = None
    limit: int = 24


class SearchHit(AssetSummary):
    score: float = 0.0


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    caption: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ForkRequest(BaseModel):
    prompt: str | None = None
    note: str = "Forked variation"


class EditRegionRequest(BaseModel):
    prompt: str
    box: list[float] = Field(..., min_length=4, max_length=4)  # [x0,y0,x1,y1] normalised 0..1


class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    model: str = "black-forest-labs/FLUX.1-schnell"
    project: str = ""
    campaign: str = ""
    tags: list[str] = Field(default_factory=list)


class CollectionIn(BaseModel):
    name: str
    description: str = ""
    kind: str = "collection"
    rule: dict[str, Any] = Field(default_factory=dict)
    asset_ids: list[str] = Field(default_factory=list)


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    kind: str
    rule: dict[str, Any]
    asset_ids: list[str]
    created_at: datetime


class OtpRequest(BaseModel):
    email: str
    name: str = ""
    password: str = ""       # required when purpose == "register"
    purpose: str = "login"   # login | register


class OtpVerify(BaseModel):
    email: str
    code: str


class PasswordLogin(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    is_active: bool
    verified: bool
    last_login: datetime | None
    created_at: datetime


class AuthResult(BaseModel):
    token: str
    user: UserOut


class RoleUpdate(BaseModel):
    role: str  # user | admin


class Stats(BaseModel):
    total_assets: int
    total_storage_bytes: int
    by_media_type: dict[str, int]
    by_provider: dict[str, int]
    huggingface_enabled: bool
    b2_enabled: bool
    generation_backend: str = "procedural"
    genblaze_version: str = "unknown"
    storage_backend: str = "local"
