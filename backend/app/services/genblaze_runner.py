"""Real Genblaze SDK orchestration.

This module drives the actual ``genblaze`` SDK (``genblaze-core`` +
``genblaze-s3``) rather than a hand-rolled pipeline:

* Generation runs through a real ``genblaze.Pipeline`` with a custom
  ``SyncProvider``, producing a cryptographically-verified provenance
  ``Manifest`` (canonical SHA-256 over the run) for every asset.
* Durable storage uses the official ``genblaze_s3.S3StorageBackend`` for
  Backblaze B2 when credentials are present, and a local ``StorageBackend``
  implementation otherwise — the same ``StorageBackend`` interface either way.

The custom provider fetches image bytes from a real generator (Hugging Face if
a token is set, else the keyless Pollinations FLUX endpoint), so prompts yield
actually-relevant images with no paid credentials required for the demo. Swap in
``genblaze_gmicloud`` / OpenAI / Stability providers by installing the extra and
setting the matching API key — the Pipeline code is unchanged.
"""
from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

import genblaze
from genblaze import (
    Asset,
    Modality,
    ObjectMetadata,
    Pipeline,
    StorageBackend,
    SyncProvider,
)

from ..config import STORAGE_DIR, get_settings
from . import generation

logger = logging.getLogger("mediadna.genblaze")

try:
    from importlib.metadata import version as _pkg_version

    _VERSION = _pkg_version("genblaze")
except Exception:  # pragma: no cover
    _VERSION = "unknown"


# --------------------------------------------------------------------------- #
# Storage backends (genblaze StorageBackend interface)
# --------------------------------------------------------------------------- #
class LocalStorageBackend(StorageBackend):
    """Filesystem implementation of the genblaze ``StorageBackend`` interface."""

    def __init__(self, root: Path = STORAGE_DIR) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put(self, key, data, *, content_type=None, metadata=None, extra_args=None):
        payload = data.read() if hasattr(data, "read") else data
        self._p(key).write_bytes(payload)
        return key

    def get(self, key):
        return self._p(key).read_bytes()

    def exists(self, key):
        return self._p(key).exists()

    def delete(self, key):
        p = self._p(key)
        if p.exists():
            p.unlink()

    def get_url(self, key, *, expires_in=3600):
        return f"local://{key}"

    def get_durable_url(self, key):
        return f"local://{key}"

    def head(self, key):
        p = self._p(key)
        if not p.exists():
            return None
        return ObjectMetadata(
            key=key, size=p.stat().st_size, content_type="application/octet-stream",
            etag="", last_modified=None, metadata={}, storage_class="",
        )


import re
from functools import lru_cache

_REGION_RE = re.compile(r"lives in ([a-z]{2}-[a-z]+-\d+)")


def _b2_backend(region: str | None):
    from genblaze_s3 import S3StorageBackend

    settings = get_settings()
    return S3StorageBackend.for_backblaze(
        settings.b2_bucket_name,
        key_id=settings.b2_key_id,
        app_key=settings.b2_app_key,
        region=region or None,
        preflight=False,
    )


@lru_cache(maxsize=1)
def _resolve_b2() -> tuple[object, str] | None:
    """Build a validated B2 backend, auto-detecting the bucket region once."""
    from genblaze_core.exceptions import StorageError

    settings = get_settings()
    region = settings.b2_region or None
    for _ in range(2):
        backend = _b2_backend(region)
        try:
            backend.put("mediadna/.probe", b"ok", content_type="text/plain")
            return backend, region or "auto"
        except StorageError as exc:
            match = _REGION_RE.search(str(exc))
            if match and region != match.group(1):
                region = match.group(1)
                logger.info("resolved B2 region -> %s", region)
                continue
            logger.warning("B2 probe failed: %s", str(exc)[:200])
            return None
        except Exception as exc:  # pragma: no cover
            logger.warning("B2 init failed: %s", str(exc)[:200])
            return None
    return None


def build_backend() -> tuple[StorageBackend, str]:
    """Return (genblaze StorageBackend, label). B2 via the official SDK if configured."""
    from .. import certs

    certs.ensure_ca_bundle()  # make boto3/requests trust the machine's roots
    settings = get_settings()
    if settings.b2_enabled:
        resolved = _resolve_b2()
        if resolved is not None:
            backend, region = resolved
            logger.info("using Backblaze B2 backend (region=%s)", region)
            return backend, "b2"
        logger.warning("B2 configured but unreachable; using local backend")
    return LocalStorageBackend(), "local"


# --------------------------------------------------------------------------- #
# Custom provider — real generator behind the genblaze SyncProvider contract
# --------------------------------------------------------------------------- #
class ImageGenProvider(SyncProvider):
    """genblaze provider that produces real images (HF -> Pollinations -> procedural)."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "genblaze-image"  # type: ignore[assignment]
        self.produced: dict | None = None

    def generate(self, step, config=None):
        raw, backend = generation.generate_image(step.prompt, step.model or "flux", seed_extra=str(step.seed or ""))
        sha = hashlib.sha256(raw).hexdigest()
        width = height = 0
        media_type = "image/png"
        try:
            img = Image.open(io.BytesIO(raw))
            width, height = img.size
            media_type = f"image/{(img.format or 'PNG').lower()}"
        except Exception:
            pass
        self.produced = {
            "bytes": raw, "sha256": sha, "width": width, "height": height,
            "media_type": media_type, "gen_backend": backend,
        }
        step.assets.append(Asset(
            url=f"mediadna://generated/{sha}.png",
            media_type=media_type, sha256=sha, size_bytes=len(raw),
            width=width, height=height,
        ))
        step.metadata = {**(step.metadata or {}), "generation_backend": backend}
        return step


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
@dataclass
class GenResult:
    raw: bytes
    sha256: str
    width: int
    height: int
    media_type: str
    manifest: dict = field(default_factory=dict)
    canonical_hash: str = ""
    run_id: str = ""
    provider: str = "genblaze-image"
    generation_backend: str = "procedural"
    manifest_verified: bool = False


def run_generation(prompt: str, model: str = "flux", modality: str = "image") -> GenResult:
    """Execute a real genblaze Pipeline and return generated bytes + verified manifest."""
    from .. import certs

    certs.ensure_ca_bundle()  # trust machine roots before any provider HTTP call
    provider = ImageGenProvider()
    result = (
        Pipeline("mediadna-generate")
        .step(provider, model=model, prompt=prompt, modality=Modality.IMAGE)
        .run(timeout=180, raise_on_failure=False)
    )

    produced = provider.produced or {}
    manifest = getattr(result, "manifest", None)
    manifest_dict: dict = {}
    canonical_hash = ""
    verified = False
    run_id = ""
    if manifest is not None:
        try:
            manifest_dict = manifest.model_dump(mode="json")
            canonical_hash = manifest.canonical_hash or ""
            verified = bool(manifest.verify())
        except Exception as exc:  # pragma: no cover
            logger.warning("manifest serialization failed: %s", exc)
    run = getattr(result, "run", None)
    if run is not None:
        run_id = getattr(run, "run_id", "") or ""

    return GenResult(
        raw=produced.get("bytes", b""),
        sha256=produced.get("sha256", ""),
        width=produced.get("width", 0),
        height=produced.get("height", 0),
        media_type=produced.get("media_type", "image/png"),
        manifest=manifest_dict,
        canonical_hash=canonical_hash,
        run_id=run_id,
        provider=provider.name,
        generation_backend=produced.get("gen_backend", "procedural"),
        manifest_verified=verified,
    )


def sdk_info() -> dict:
    settings = get_settings()
    return {
        "genblaze_version": _VERSION,
        "storage_backend": "b2" if settings.b2_enabled else "local",
    }
