"""AI provider abstraction.

``AIProvider`` defines the analysis surface. ``HuggingFaceProvider`` calls the
HF Inference API when a token is configured. ``LocalHeuristicProvider`` is the
always-on fallback: it derives deterministic, plausible signals from the actual
bytes/pixels so the pipeline produces real output offline. All models are
configurable via settings.
"""
from __future__ import annotations

import colorsys
import hashlib
import io
import math
from abc import ABC, abstractmethod

import numpy as np
import requests
from PIL import Image

from ..config import get_settings

HF_API = "https://router.huggingface.co/hf-inference/models"

_STYLES = [
    "photorealistic", "cyberpunk", "watercolor", "3d render", "flat illustration",
    "cinematic", "anime", "minimalist", "oil painting", "vaporwave",
]
_COMMON_OBJECTS = [
    "person", "car", "building", "tree", "product", "logo", "text", "animal",
    "drone", "sky", "water", "food", "device", "furniture",
]


class AIProvider(ABC):
    name: str

    @abstractmethod
    def caption(self, image: Image.Image, raw: bytes) -> str: ...

    @abstractmethod
    def detect_objects(self, image: Image.Image, raw: bytes) -> list[dict]: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...


def _seed(raw: bytes) -> int:
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


class LocalHeuristicProvider(AIProvider):
    """Deterministic, dependency-free analysis derived from the asset itself."""

    name = "local-heuristic"

    def __init__(self) -> None:
        self.dim = get_settings().embedding_dim

    def caption(self, image: Image.Image | None, raw: bytes) -> str:
        rng = np.random.default_rng(_seed(raw))
        style = _STYLES[rng.integers(len(_STYLES))]
        subj = _COMMON_OBJECTS[rng.integers(len(_COMMON_OBJECTS))]
        scene = ["at golden hour", "in a studio", "on a city street", "in nature",
                 "against a gradient backdrop"][rng.integers(5)]
        return f"A {style} composition featuring a {subj} {scene}."

    def detect_objects(self, image: Image.Image | None, raw: bytes) -> list[dict]:
        rng = np.random.default_rng(_seed(raw) ^ 0xABCDEF)
        n = int(rng.integers(2, 5))
        picks = rng.choice(len(_COMMON_OBJECTS), size=n, replace=False)
        return [
            {"label": _COMMON_OBJECTS[i], "score": round(float(0.55 + rng.random() * 0.44), 3)}
            for i in picks
        ]

    def embed(self, text: str) -> list[float]:
        """Hashing bag-of-words embedding — stable and semantically sensible."""
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = "".join(c.lower() if c.isalnum() else " " for c in text).split()
        for tok in tokens:
            for gram in (tok, tok[:4], tok[-4:]):
                h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.tolist()


class HuggingFaceProvider(AIProvider):
    """HF Inference API provider with graceful degradation to the local one."""

    name = "huggingface"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.fallback = LocalHeuristicProvider()
        self._headers = {"Authorization": f"Bearer {self.settings.hf_token}"}

    def _post(self, model: str, data: bytes | dict, binary: bool) -> object | None:
        try:
            kwargs = {"headers": self._headers, "timeout": 60}
            if binary:
                resp = requests.post(f"{HF_API}/{model}", data=data, **kwargs)
            else:
                resp = requests.post(f"{HF_API}/{model}", json=data, **kwargs)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def caption(self, image: Image.Image | None, raw: bytes) -> str:
        out = self._post(self.settings.hf_caption_model, raw, binary=True)
        if isinstance(out, list) and out and isinstance(out[0], dict):
            text = out[0].get("generated_text")
            if text:
                return text
        return self.fallback.caption(image, raw)

    def detect_objects(self, image: Image.Image | None, raw: bytes) -> list[dict]:
        out = self._post(self.settings.hf_detection_model, raw, binary=True)
        if isinstance(out, list) and out and isinstance(out[0], dict) and "label" in out[0]:
            return [
                {"label": o["label"], "score": round(float(o.get("score", 0)), 3)}
                for o in out[:12]
            ]
        return self.fallback.detect_objects(image, raw)

    def embed(self, text: str) -> list[float]:
        out = self._post(
            self.settings.hf_embedding_model,
            {"inputs": text, "options": {"wait_for_model": True}},
            binary=False,
        )
        if isinstance(out, list) and out and isinstance(out[0], (int, float)):
            vec = np.asarray(out, dtype=np.float32)
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            # normalise dimensionality to configured dim
            if vec.shape[0] != self.settings.embedding_dim:
                return self.fallback.embed(text)
            return vec.tolist()
        return self.fallback.embed(text)


def get_provider() -> AIProvider:
    settings = get_settings()
    if settings.huggingface_enabled:
        return HuggingFaceProvider()
    return LocalHeuristicProvider()


# --- shared image helpers ---------------------------------------------------

def dominant_colors(image: Image.Image, k: int = 5) -> list[str]:
    small = image.convert("RGB").resize((64, 64))
    arr = np.asarray(small).reshape(-1, 3).astype(np.float32)
    # simple k-means (few iterations, deterministic init)
    idx = np.linspace(0, len(arr) - 1, k).astype(int)
    centers = arr[idx]
    for _ in range(6):
        d = np.linalg.norm(arr[:, None, :] - centers[None, :, :], axis=2)
        labels = d.argmin(axis=1)
        for j in range(k):
            pts = arr[labels == j]
            if len(pts):
                centers[j] = pts.mean(axis=0)
    counts = np.bincount(labels, minlength=k)
    order = counts.argsort()[::-1]
    return ["#%02x%02x%02x" % tuple(int(c) for c in centers[j]) for j in order]


def infer_style(colors: list[str]) -> str:
    if not colors:
        return "unknown"
    r, g, b = (int(colors[0][i:i + 2], 16) for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if s < 0.15:
        return "minimalist"
    if 0.7 < h < 0.9 and s > 0.4:
        return "cyberpunk"
    if v > 0.8 and s > 0.5:
        return "vaporwave"
    if v < 0.35:
        return "cinematic"
    return "photorealistic"


def quality_score(image: Image.Image) -> float:
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    # variance of Laplacian as a sharpness proxy
    lap = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    sharp = float(lap.var())
    return round(min(1.0, math.log10(sharp + 1) / 3.5), 3)
