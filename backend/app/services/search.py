"""Semantic search + relationship/duplicate detection.

Combines embedding cosine similarity with lightweight metadata filters and
keyword scoring. The same embedding space is used to auto-detect near-duplicates
and version relationships at ingest time.
"""
from __future__ import annotations

import numpy as np

from ..models import Asset


def _vec(a: Asset) -> np.ndarray:
    v = np.asarray(a.embedding or [], dtype=np.float32)
    return v


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def keyword_score(asset: Asset, query: str) -> float:
    if not query:
        return 0.0
    q = query.lower()
    haystack = " ".join([
        asset.name, asset.caption, asset.prompt, asset.model, asset.provider,
        asset.project, asset.campaign, asset.visual_style,
        " ".join(asset.tags or []),
        " ".join(o.get("label", "") for o in (asset.objects_detected or [])),
    ]).lower()
    terms = [t for t in q.replace(",", " ").split() if len(t) > 1]
    if not terms:
        return 0.0
    hits = sum(1 for t in terms if t in haystack)
    return hits / len(terms)


def search(
    assets: list[Asset],
    query_embedding: list[float],
    query: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
    tag: str | None = None,
) -> list[tuple[Asset, float]]:
    qv = np.asarray(query_embedding, dtype=np.float32)
    scored: list[tuple[Asset, float]] = []
    for a in assets:
        if provider and a.provider.lower() != provider.lower():
            continue
        if model and model.lower() not in a.model.lower():
            continue
        if project and a.project.lower() != project.lower():
            continue
        if tag and tag.lower() not in [t.lower() for t in (a.tags or [])]:
            continue
        sim = cosine(qv, _vec(a)) if query else 0.0
        kw = keyword_score(a, query)
        score = 0.65 * sim + 0.35 * kw if query else 1.0
        scored.append((a, round(score, 4)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def find_relationships(new_asset: Asset, existing: list[Asset]) -> list[tuple[str, str, float]]:
    """Return (target_id, kind, score) edges to create for a newly ingested asset."""
    edges: list[tuple[str, str, float]] = []
    nv = _vec(new_asset)
    for other in existing:
        if other.id == new_asset.id:
            continue
        if other.checksum and other.checksum == new_asset.checksum:
            edges.append((other.id, "duplicate_of", 1.0))
            continue
        sim = cosine(nv, _vec(other))
        if sim >= 0.92:
            edges.append((other.id, "near_duplicate", sim))
        elif sim >= 0.75:
            edges.append((other.id, "related_to", sim))
    edges.sort(key=lambda e: e[2], reverse=True)
    return edges[:6]
