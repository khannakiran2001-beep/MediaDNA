"""Seed MediaDNA with demo assets so the graph, search and lineage light up.

Generates synthetic images with Pillow (no downloads needed), ingests them
through the real Genblaze pipeline, then forks a couple to create lineage.

Usage:  python scripts/seed.py
"""
from __future__ import annotations

import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from PIL import Image, ImageDraw  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.asset_service import AssetService  # noqa: E402

DEMO = [
    ("neon_city.png", "cyberpunk city street at night, neon signs, rain", "FLUX.1-dev", "Genblaze", "Summer Launch", "summer", ["cyberpunk", "city", "neon"], (20, 8, 60)),
    ("product_shot.png", "minimalist product photo of a sneaker on gradient", "SDXL", "Genblaze", "Summer Launch", "summer", ["product", "sneaker", "studio"], (240, 240, 245)),
    ("drone_valley.png", "aerial drone shot over a green valley, cinematic", "FLUX.1-dev", "Genblaze", "Nature Series", "q3", ["drone", "aerial", "nature"], (30, 90, 40)),
    ("portrait_ai.png", "photorealistic portrait of a person, soft light", "SDXL", "Genblaze", "Brand Faces", "q3", ["portrait", "person"], (120, 90, 80)),
    ("logo_concept.png", "flat vector logo concept, bold geometric", "Ideogram", "Genblaze", "Rebrand", "brand", ["logo", "vector", "brand"], (250, 200, 40)),
    ("vapor_poster.png", "vaporwave poster, pink and cyan, retro grid", "FLUX.1-dev", "Genblaze", "Summer Launch", "summer", ["vaporwave", "poster", "retro"], (255, 80, 200)),
]


def make_image(color: tuple[int, int, int], label: str) -> bytes:
    rng = random.Random(label)
    img = Image.new("RGB", (768, 512), color)
    d = ImageDraw.Draw(img)
    for _ in range(24):
        x0, y0 = rng.randint(0, 768), rng.randint(0, 512)
        x1, y1 = x0 + rng.randint(20, 220), y0 + rng.randint(20, 180)
        c = tuple(min(255, v + rng.randint(-40, 80)) for v in color)
        d.rectangle([x0, y0, x1, y1], fill=c)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> None:
    init_db()
    db = SessionLocal()
    svc = AssetService(db)
    created = []
    for name, prompt, model, provider, project, campaign, tags, color in DEMO:
        raw = make_image(color, name)
        a = svc.ingest(
            filename=name, raw=raw, mime_type="image/png", prompt=prompt,
            model=model, provider_name=provider, project=project, campaign=campaign, tags=tags,
        )
        created.append(a)
        print(f"  [ok] ingested {name}  ({a.visual_style}, q={a.quality_score})")

    # build lineage: fork the neon city twice (v2, v3), fork product once
    svc.fork(created[0].id, "cyberpunk city, upscaled 4k, more neon", "Upscaled")
    svc.fork(created[0].id, "cyberpunk city, added flying cars", "Edited variation")
    svc.fork(created[1].id, "product photo, alternate angle", "Alt angle")
    print("  [ok] created 3 forked versions (lineage)")
    db.close()
    print("\nDone. Start the server and open http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
