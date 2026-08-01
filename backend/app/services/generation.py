"""Genblaze generation — text-to-media.

Backends, tried in order:
  1. Hugging Face Inference API  (if ``HF_TOKEN`` is set)
  2. Pollinations                (free, no API key — real FLUX/SDXL images)
  3. Procedural renderer         (deterministic, offline last resort)

The output bytes then flow through the same Genblaze analysis pipeline as an
upload. All network calls verify TLS by default and transparently retry without
verification if the local network breaks the cert chain (SSL inspection).
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
from urllib.parse import quote

import numpy as np
import requests
import urllib3
from PIL import Image, ImageDraw, ImageFilter

from ..config import get_settings

logger = logging.getLogger("mediadna.generation")

HF_API = "https://router.huggingface.co/hf-inference/models"
POLLINATIONS_API = "https://image.pollinations.ai/prompt"


def _get(url: str, **kwargs) -> requests.Response | None:
    """GET with TLS verification, auto-retrying insecurely on cert failure."""
    settings = get_settings()
    try:
        return requests.get(url, verify=settings.ssl_verify, **kwargs)
    except requests.exceptions.SSLError:
        logger.warning("TLS verification failed for %s — retrying without verify", url.split("?")[0])
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            return requests.get(url, verify=False, **kwargs)
        except Exception as exc:  # pragma: no cover
            logger.error("insecure retry failed: %s", exc)
            return None
    except Exception as exc:  # pragma: no cover
        logger.error("request failed: %s", exc)
        return None

# keyword -> base palette (RGB) used by the procedural fallback
_PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "cyberpunk": [(18, 6, 48), (124, 58, 237), (34, 211, 238), (255, 45, 149)],
    "neon": [(10, 5, 30), (255, 0, 128), (0, 255, 200), (120, 0, 255)],
    "vaporwave": [(40, 10, 60), (255, 90, 200), (90, 220, 255), (255, 210, 120)],
    "nature": [(20, 60, 30), (90, 160, 70), (200, 210, 120), (60, 120, 80)],
    "drone": [(30, 80, 90), (120, 180, 160), (200, 220, 210), (60, 110, 120)],
    "ocean": [(6, 40, 80), (20, 120, 170), (120, 210, 230), (10, 70, 120)],
    "sunset": [(70, 20, 60), (240, 120, 60), (255, 200, 90), (180, 60, 90)],
    "portrait": [(60, 45, 40), (180, 140, 120), (230, 200, 180), (90, 70, 60)],
    "minimalist": [(240, 240, 245), (210, 210, 220), (180, 185, 200), (120, 130, 150)],
    "product": [(235, 236, 240), (200, 205, 215), (140, 150, 170), (90, 100, 120)],
    "logo": [(250, 200, 40), (30, 30, 40), (240, 240, 245), (120, 90, 240)],
    "fire": [(60, 10, 10), (220, 70, 20), (255, 180, 40), (150, 30, 20)],
    "forest": [(15, 45, 25), (40, 90, 45), (110, 150, 80), (200, 210, 150)],
}
_DEFAULT_PALETTE = [(20, 20, 40), (90, 90, 160), (150, 150, 220), (60, 60, 110)]


def _palette_for(prompt: str) -> list[tuple[int, int, int]]:
    p = prompt.lower()
    for key, pal in _PALETTES.items():
        if key in p:
            return pal
    return _DEFAULT_PALETTE


def _procedural_image(prompt: str, seed_extra: str = "") -> bytes:
    """Deterministic abstract art derived from the prompt — varies per prompt."""
    seed = int.from_bytes(hashlib.sha256((prompt + seed_extra).encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    pal = _palette_for(prompt)
    w, h = 768, 512

    # base vertical gradient between two palette colours
    top = np.array(pal[0], dtype=np.float32)
    bottom = np.array(pal[rng.integers(1, len(pal))], dtype=np.float32)
    grad = np.linspace(0, 1, h)[:, None, None]
    base = (top[None, None, :] * (1 - grad) + bottom[None, None, :] * grad)
    arr = np.repeat(base, w, axis=1).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # scattered translucent geometry seeded by the prompt
    shapes = int(18 + (seed % 22))
    for _ in range(shapes):
        c = pal[rng.integers(len(pal))]
        alpha = int(rng.integers(60, 190))
        x0, y0 = int(rng.integers(0, w)), int(rng.integers(0, h))
        size = int(rng.integers(30, 260))
        kind = rng.integers(3)
        fill = (c[0], c[1], c[2], alpha)
        if kind == 0:
            draw.ellipse([x0, y0, x0 + size, y0 + size], fill=fill)
        elif kind == 1:
            draw.rectangle([x0, y0, x0 + size, y0 + int(size * 0.6)], fill=fill)
        else:
            pts = [(int(rng.integers(0, w)), int(rng.integers(0, h))) for _ in range(3)]
            draw.polygon(pts, fill=fill)

    # subtle glow / depth
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(6)), 0.35)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _hf_text_to_image(prompt: str, model: str) -> bytes | None:
    settings = get_settings()
    try:
        resp = requests.post(
            f"{HF_API}/{model}",
            headers={"Authorization": f"Bearer {settings.hf_token}"},
            json={"inputs": prompt, "options": {"wait_for_model": True}},
            timeout=120,
            verify=settings.ssl_verify,
        )
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            return resp.content
    except Exception as exc:
        logger.warning("HF text-to-image failed: %s", exc)
    return None


def _pollinations_image(prompt: str, seed_extra: str) -> bytes | None:
    """Free, keyless text-to-image (FLUX/SDXL server-side), with retries."""
    settings = get_settings()
    base_seed = int.from_bytes(hashlib.sha256((prompt + seed_extra).encode()).digest()[:4], "big")
    # Pollinations occasionally 500s under load; retry with nudged seeds.
    for attempt in range(3):
        seed = (base_seed + attempt * 7919) % 2_000_000_000
        url = (
            f"{POLLINATIONS_API}/{quote(prompt)}"
            f"?width={settings.gen_width}&height={settings.gen_height}"
            f"&nologo=true&seed={seed}&model={settings.pollinations_model}"
        )
        resp = _get(url, timeout=150)
        if resp is not None and resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            return resp.content
        if resp is not None:
            logger.warning("Pollinations attempt %d returned %s (%s)", attempt + 1, resp.status_code, resp.headers.get("content-type"))
    return None


def generate_image(prompt: str, model: str = "black-forest-labs/FLUX.1-schnell", seed_extra: str = "") -> tuple[bytes, str]:
    """Return (image_bytes, backend_label).

    Tries a real generator (HF → Pollinations) before the procedural fallback,
    so prompts produce actually-relevant images with no credentials required.
    """
    settings = get_settings()

    if settings.huggingface_enabled:
        data = _hf_text_to_image(prompt, model)
        if data:
            return data, "huggingface"

    if settings.pollinations_enabled:
        data = _pollinations_image(prompt, seed_extra)
        if data:
            return data, "pollinations"

    logger.info("Falling back to procedural generation for prompt: %s", prompt[:60])
    return _procedural_image(prompt, seed_extra), "procedural"
