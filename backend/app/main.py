"""MediaDNA API — FastAPI application.

Serves the JSON API and the single-page frontend. Storage bytes are streamed
through the API so Backblaze credentials never reach the client.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_admin
from .config import get_settings
from .database import SessionLocal, get_db, init_db
from .models import Collection, User
from .repositories import (
    AssetRepository,
    AuditRepository,
    CollectionRepository,
    CommentRepository,
    RelationshipRepository,
)
from .schemas import (
    AssetDetail,
    AssetSummary,
    AuthResult,
    CollectionIn,
    CollectionOut,
    CommentIn,
    CommentOut,
    EditRegionRequest,
    ForkRequest,
    GenerateRequest,
    GraphResponse,
    OtpRequest,
    OtpVerify,
    PasswordLogin,
    RoleUpdate,
    SearchRequest,
    SearchHit,
    Stats,
    UserOut,
)
from .services import genblaze_runner
from .services import search as search_service
from .services.asset_service import AssetService
from .services.auth_service import AuthError, AuthService
from .services.providers import get_provider
from .services.storage import get_storage

settings = get_settings()
app = FastAPI(title="MediaDNA API", version="1.0.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.on_event("startup")
def _startup() -> None:
    from . import certs

    certs.ensure_ca_bundle()
    init_db()
    db = SessionLocal()
    try:
        AuthService(db).ensure_default_admin()
    finally:
        db.close()


# --- Auth gate --------------------------------------------------------------
# Public: auth endpoints, health, the SPA, and the browser-loaded media routes
# (/file, /thumbnail) which can't send an Authorization header and are guarded
# by the unguessable asset id + short-lived signed B2 URL.

def _is_public(path: str) -> bool:
    if not path.startswith("/api/"):
        return True
    if path.startswith(("/api/auth", "/api/health")):
        return True
    if path.endswith(("/thumbnail", "/file")):
        return True
    return False


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if _is_public(request.url.path):
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    db = SessionLocal()
    try:
        user = AuthService(db).user_for_token(token)
    finally:
        db.close()
    if user is None:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    request.state.user_id = user.id
    request.state.user_email = user.email
    request.state.user_role = user.role
    return await call_next(request)


# --- Authentication ---------------------------------------------------------

@app.post("/api/auth/request-otp")
def auth_request_otp(body: OtpRequest, db: Session = Depends(get_db)):
    try:
        return AuthService(db).request_otp(body.email, body.name, body.purpose)
    except AuthError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/auth/verify", response_model=AuthResult)
def auth_verify(body: OtpVerify, db: Session = Depends(get_db)):
    try:
        user, token = AuthService(db).verify_otp(body.email, body.code)
    except AuthError as exc:
        raise HTTPException(400, str(exc))
    return {"token": token, "user": user}


@app.post("/api/auth/login-password", response_model=AuthResult)
def auth_login_password(body: PasswordLogin, db: Session = Depends(get_db)):
    try:
        user, token = AuthService(db).login_password(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(400, str(exc))
    return {"token": token, "user": user}


@app.get("/api/auth/me", response_model=UserOut)
def auth_me(user: User = Depends(get_current_user)):
    return user


@app.post("/api/auth/logout")
def auth_logout(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    AuthService(db).logout(token)
    return {"ok": True}


# --- Admin ------------------------------------------------------------------

@app.get("/api/admin/users", response_model=list[UserOut])
def admin_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@app.post("/api/admin/users/{user_id}/role", response_model=UserOut)
def admin_set_role(
    user_id: str, body: RoleUpdate,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    if body.role not in ("user", "admin"):
        raise HTTPException(400, "Invalid role")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == admin.id and body.role != "admin":
        raise HTTPException(400, "You cannot demote yourself")
    target.role = body.role
    db.commit()
    AuditRepository(db).log("admin_set_role", None, {"user": target.email, "role": body.role, "by": admin.email})
    db.refresh(target)
    return target


@app.post("/api/admin/users/{user_id}/active", response_model=UserOut)
def admin_toggle_active(
    user_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == admin.id:
        raise HTTPException(400, "You cannot deactivate yourself")
    target.is_active = not target.is_active
    db.commit()
    db.refresh(target)
    return target


@app.post("/api/admin/assets/{asset_id}/approval", response_model=AssetDetail)
def admin_set_approval(
    asset_id: str, status: str,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    if status not in ("approved", "rejected", "pending"):
        raise HTTPException(400, "Invalid status")
    repo = AssetRepository(db)
    asset = repo.get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.approval_status = status
    repo.save(asset)
    AuditRepository(db).log("approval", asset_id, {"status": status, "by": admin.email})
    return asset


# --- Assets -----------------------------------------------------------------

@app.post("/api/assets", response_model=AssetDetail)
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    prompt: str = Form(""),
    negative_prompt: str = Form(""),
    model: str = Form(""),
    provider: str = Form(""),
    project: str = Form(""),
    campaign: str = Form(""),
    tags: str = Form(""),
    parent_id: str = Form(""),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    svc = AssetService(db)
    asset = svc.ingest(
        filename=file.filename or "asset",
        raw=raw,
        mime_type=file.content_type or "",
        prompt=prompt,
        negative_prompt=negative_prompt,
        model=model,
        provider_name=provider,
        project=project,
        campaign=campaign,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        parent_id=parent_id or None,
        owner_id=getattr(request.state, "user_id", None),
        owner_email=getattr(request.state, "user_email", ""),
    )
    return asset


@app.post("/api/generate", response_model=AssetDetail)
def generate_asset(request: Request, body: GenerateRequest, db: Session = Depends(get_db)):
    if not body.prompt.strip():
        raise HTTPException(400, "Prompt is required")
    svc = AssetService(db)
    asset = svc.generate(
        prompt=body.prompt,
        negative_prompt=body.negative_prompt,
        model=body.model,
        project=body.project,
        campaign=body.campaign,
        tags=[t.strip() for t in body.tags if t.strip()],
        owner_id=getattr(request.state, "user_id", None),
        owner_email=getattr(request.state, "user_email", ""),
    )
    return asset


@app.get("/api/assets", response_model=list[AssetSummary])
def list_assets(limit: int = 100, db: Session = Depends(get_db)):
    return AssetRepository(db).list(limit)


@app.get("/api/assets/{asset_id}", response_model=AssetDetail)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = AssetRepository(db).get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset


@app.get("/api/assets/{asset_id}/file")
def get_asset_file(asset_id: str, db: Session = Depends(get_db)):
    repo = AssetRepository(db)
    asset = repo.get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.downloads += 1
    repo.save(asset)
    storage = get_storage()
    url = storage.presigned_url(asset.storage_key)
    if url:  # signed B2 URL — browser fetches directly from Backblaze
        return RedirectResponse(url)
    data = storage.get(asset.storage_key)
    return Response(content=data, media_type=asset.mime_type or "application/octet-stream")


@app.get("/api/assets/{asset_id}/thumbnail")
def get_thumbnail(asset_id: str, db: Session = Depends(get_db)):
    asset = AssetRepository(db).get(asset_id)
    if not asset or not asset.thumbnail_key:
        raise HTTPException(404, "No thumbnail")
    storage = get_storage()
    url = storage.presigned_url(asset.thumbnail_key)
    if url:  # signed B2 URL — browser fetches directly from Backblaze
        return RedirectResponse(url)
    return Response(content=storage.get(asset.thumbnail_key), media_type="image/jpeg")


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    repo = AssetRepository(db)
    asset = repo.get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    AuditRepository(db).log("delete", asset_id, {"name": asset.name})
    repo.delete(asset)
    return {"deleted": asset_id}


# --- Versions & lineage -----------------------------------------------------

@app.get("/api/assets/{asset_id}/versions", response_model=list[AssetSummary])
def versions(asset_id: str, db: Session = Depends(get_db)):
    repo = AssetRepository(db)
    asset = repo.get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return repo.versions_of(asset.root_id or asset.id)


@app.post("/api/assets/{asset_id}/fork", response_model=AssetDetail)
def fork_asset(request: Request, asset_id: str, body: ForkRequest, db: Session = Depends(get_db)):
    child = AssetService(db).fork(
        asset_id, body.prompt, body.note,
        owner_id=getattr(request.state, "user_id", None),
        owner_email=getattr(request.state, "user_email", ""),
    )
    if not child:
        raise HTTPException(404, "Asset not found")
    return child


@app.post("/api/assets/{asset_id}/edit-region", response_model=AssetDetail)
def edit_region(request: Request, asset_id: str, body: EditRegionRequest, db: Session = Depends(get_db)):
    if not body.prompt.strip():
        raise HTTPException(400, "Prompt is required")
    child = AssetService(db).edit_region(
        asset_id, body.prompt, body.box,
        owner_id=getattr(request.state, "user_id", None),
        owner_email=getattr(request.state, "user_email", ""),
    )
    if not child:
        raise HTTPException(404, "Asset not found or not an image")
    return child


@app.get("/api/assets/{asset_id}/related", response_model=list[AssetSummary])
def related(asset_id: str, db: Session = Depends(get_db)):
    repo = AssetRepository(db)
    rels = RelationshipRepository(db).for_asset(asset_id)
    ids = {r.source_id for r in rels} | {r.target_id for r in rels}
    ids.discard(asset_id)
    return [a for a in (repo.get(i) for i in ids) if a]


# --- Comments ---------------------------------------------------------------

@app.get("/api/assets/{asset_id}/comments", response_model=list[CommentOut])
def get_comments(asset_id: str, db: Session = Depends(get_db)):
    return CommentRepository(db).for_asset(asset_id)


@app.post("/api/assets/{asset_id}/comments", response_model=CommentOut)
def add_comment(request: Request, asset_id: str, body: CommentIn, db: Session = Depends(get_db)):
    if not AssetRepository(db).get(asset_id):
        raise HTTPException(404, "Asset not found")
    author = getattr(request.state, "user_email", "") or body.author
    return CommentRepository(db).add(asset_id, author, body.body)


# --- Search -----------------------------------------------------------------

@app.post("/api/search", response_model=list[SearchHit])
def semantic_search(req: SearchRequest, db: Session = Depends(get_db)):
    assets = AssetRepository(db).all()
    provider = get_provider()
    qemb = provider.embed(req.query) if req.query else []
    ranked = search_service.search(
        assets, qemb, req.query,
        provider=req.provider, model=req.model, project=req.project, tag=req.tag,
    )
    hits = []
    for asset, score in ranked[: req.limit]:
        hit = SearchHit.model_validate(asset)
        hit.score = score
        hits.append(hit)
    return hits


# --- Graph ------------------------------------------------------------------

@app.get("/api/graph", response_model=GraphResponse)
def graph(db: Session = Depends(get_db)):
    assets = AssetRepository(db).all()
    edges = RelationshipRepository(db).all()
    nodes = [
        {"id": a.id, "label": a.name[:28], "type": a.media_type, "caption": a.caption}
        for a in assets
    ]
    graph_edges = [{"source": e.source_id, "target": e.target_id, "kind": e.kind} for e in edges]
    return {"nodes": nodes, "edges": graph_edges}


# --- Collections ------------------------------------------------------------

@app.get("/api/collections", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    return CollectionRepository(db).all()


@app.post("/api/collections", response_model=CollectionOut)
def create_collection(body: CollectionIn, db: Session = Depends(get_db)):
    coll = Collection(**body.model_dump())
    return CollectionRepository(db).add(coll)


# --- Dashboard / stats ------------------------------------------------------

@app.get("/api/stats", response_model=Stats)
def stats(db: Session = Depends(get_db)):
    assets = AssetRepository(db).all()
    by_type: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    total_bytes = 0
    effective_gen: str | None = None
    for a in assets:
        by_type[a.media_type] = by_type.get(a.media_type, 0) + 1
        by_provider[a.provider] = by_provider.get(a.provider, 0) + 1
        total_bytes += a.size_bytes
        if effective_gen is None:
            gb = (a.generation_params or {}).get("generation_backend")
            if gb:
                effective_gen = gb  # most recent generation's real backend
    return {
        "total_assets": len(assets),
        "total_storage_bytes": total_bytes,
        "by_media_type": by_type,
        "by_provider": by_provider,
        "huggingface_enabled": settings.huggingface_enabled,
        "b2_enabled": settings.b2_enabled,
        "generation_backend": effective_gen or (
            "huggingface" if settings.huggingface_enabled
            else "pollinations" if settings.pollinations_enabled
            else "procedural"
        ),
        **genblaze_runner.sdk_info(),
    }


@app.get("/api/activity")
def activity(db: Session = Depends(get_db)):
    logs = AuditRepository(db).recent()
    return [
        {"action": l.action, "asset_id": l.asset_id, "detail": l.detail, "at": l.created_at.isoformat()}
        for l in logs
    ]


@app.get("/api/health")
def health():
    return {"status": "ok", "huggingface": settings.huggingface_enabled, "b2": settings.b2_enabled}


# --- Frontend (served last so /api takes precedence) ------------------------

@app.get("/")
def landing():
    return FileResponse(FRONTEND_DIR / "landing.html")


@app.get("/app")
def app_spa():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
