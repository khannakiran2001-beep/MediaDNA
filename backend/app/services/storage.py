"""Storage abstraction — backed by the official Genblaze storage SDK.

All bytes (originals, thumbnails, provenance) flow through a genblaze
``StorageBackend``: the official ``genblaze_s3.S3StorageBackend`` for Backblaze
B2 when credentials are configured, and a local ``StorageBackend`` otherwise.

``get_storage()`` returns a thin adapter exposing ``put(key, data, content_type)``
and ``get(key)`` so application/repository code stays storage-agnostic.
Credentials never reach the client — bytes are streamed through the API.
"""
from __future__ import annotations

import logging

from .genblaze_runner import LocalStorageBackend, build_backend

logger = logging.getLogger("mediadna.storage")


class StorageAdapter:
    """Adapts a genblaze ``StorageBackend`` to the app's storage interface."""

    def __init__(self, backend, name: str) -> None:
        self._backend = backend
        self.name = name

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        return self._backend.put(key, data, content_type=content_type)

    def get(self, key: str) -> bytes:
        return self._backend.get(key)

    def exists(self, key: str) -> bool:
        try:
            return self._backend.exists(key)
        except Exception:
            return False

    def presigned_url(self, key: str, expires_in: int = 3600) -> str | None:
        """Return a short-lived signed HTTPS URL (B2), or None for local storage."""
        for method in ("presigned_get_url", "get_url"):
            fn = getattr(self._backend, method, None)
            if fn is None:
                continue
            try:
                url = fn(key, expires_in=expires_in)
            except TypeError:
                try:
                    url = fn(key)
                except Exception:
                    continue
            except Exception:
                continue
            if url and str(url).startswith(("http://", "https://")):
                return url
        return None


def get_storage() -> StorageAdapter:
    try:
        backend, name = build_backend()
        return StorageAdapter(backend, name)
    except Exception as exc:  # pragma: no cover - always fall back to local
        logger.warning("storage init failed (%s); using local", exc)
        return StorageAdapter(LocalStorageBackend(), "local")
