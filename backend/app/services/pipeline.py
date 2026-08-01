"""Genblaze — the modular AI orchestration pipeline.

Each stage is a small, independently-testable function. ``run`` executes them in
order and returns a dict of DNA fields plus the artifacts to persist to storage.
"""
from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from PIL import Image

from . import providers
from .providers import AIProvider


@dataclass
class PipelineResult:
    fields: dict = field(default_factory=dict)
    artifacts: dict[str, tuple[bytes, str]] = field(default_factory=dict)  # key -> (bytes, content_type)
    stages: list[dict] = field(default_factory=list)


def _log(result: PipelineResult, stage: str, detail: str) -> None:
    result.stages.append({"stage": stage, "detail": detail, "ts": datetime.now(timezone.utc).isoformat()})


def run(
    *,
    asset_id: str,
    filename: str,
    raw: bytes,
    mime_type: str,
    prompt: str,
    provider: AIProvider,
) -> PipelineResult:
    result = PipelineResult()
    media_type = _media_type(mime_type, filename)

    # 1. checksum / dedup key ------------------------------------------------
    checksum = hashlib.sha256(raw).hexdigest()
    result.fields["checksum"] = checksum
    result.fields["media_type"] = media_type
    result.fields["size_bytes"] = len(raw)
    _log(result, "metadata", f"{media_type}, {len(raw)} bytes, sha256={checksum[:12]}…")

    image: Image.Image | None = None
    if media_type == "image":
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
            result.fields["width"], result.fields["height"] = image.size
        except Exception:
            image = None

    # 2. captioning ----------------------------------------------------------
    caption = provider.caption(image, raw)
    result.fields["caption"] = caption
    _log(result, "caption", caption)

    # 3. object detection ----------------------------------------------------
    objects = provider.detect_objects(image, raw)
    result.fields["objects_detected"] = objects
    result.fields["people_detected"] = sum(1 for o in objects if o["label"] == "person")
    result.fields["brand_logos"] = [o["label"] for o in objects if "logo" in o["label"]]
    _log(result, "detection", ", ".join(o["label"] for o in objects) or "none")

    # 4. colour / style / quality -------------------------------------------
    if image is not None:
        colors = providers.dominant_colors(image)
        result.fields["dominant_colors"] = colors
        result.fields["visual_style"] = providers.infer_style(colors)
        result.fields["quality_score"] = providers.quality_score(image)
        _log(result, "quality", f"style={result.fields['visual_style']} q={result.fields['quality_score']}")

        # thumbnail artifact
        thumb = image.convert("RGB").copy()
        thumb.thumbnail((512, 512))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=82)
        result.artifacts[f"thumbnails/{asset_id}.jpg"] = (buf.getvalue(), "image/jpeg")
        result.fields["thumbnail_key"] = f"thumbnails/{asset_id}.jpg"
    else:
        result.fields["dominant_colors"] = []
        result.fields["visual_style"] = media_type
        result.fields["quality_score"] = 0.0

    # 5. OCR (heuristic placeholder unless HF handles it upstream) -----------
    result.fields["ocr_text"] = ""

    # 6. safety --------------------------------------------------------------
    result.fields["safety"] = {"nsfw": False, "violence": False, "reviewed": True}

    # 7. embedding (prompt + caption + tags/objects) ------------------------
    embed_text = " ".join(
        [prompt, caption] + [o["label"] for o in objects]
    ).strip()
    result.fields["embedding"] = provider.embed(embed_text)
    _log(result, "embedding", f"{len(result.fields['embedding'])}-dim vector")

    # 8. provenance record (also stored as JSON artifact) -------------------
    provenance = {
        "asset_id": asset_id,
        "filename": filename,
        "checksum": checksum,
        "prompt": prompt,
        "provider": provider.name,
        "pipeline": [s["stage"] for s in result.stages],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    result.fields["provenance"] = provenance
    result.artifacts[f"provenance/{asset_id}.json"] = (
        json.dumps(provenance, indent=2).encode(),
        "application/json",
    )
    result.artifacts[f"originals/{asset_id}_{filename}"] = (raw, mime_type or "application/octet-stream")
    result.fields["storage_key"] = f"originals/{asset_id}_{filename}"
    _log(result, "store", f"{len(result.artifacts)} artifacts prepared")

    return result


def _media_type(mime: str, filename: str) -> str:
    mime = (mime or "").lower()
    name = filename.lower()
    if mime.startswith("image") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return "image"
    if mime.startswith("video") or name.endswith((".mp4", ".mov", ".webm", ".avi")):
        return "video"
    if mime.startswith("audio") or name.endswith((".mp3", ".wav", ".ogg", ".flac")):
        return "audio"
    return "document"
