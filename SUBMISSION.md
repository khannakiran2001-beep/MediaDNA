# MediaDNA — Hackathon Submission

**GitHub for AI Assets** — every AI-generated image, video, audio, or document gets a permanent
identity, complete lineage, and searchable history, with cryptographically verified provenance.

- **Live app:** `https://<your-service>.onrender.com`  ·  **Landing:** `/`  ·  **App:** `/app`
- **Repo:** https://github.com/khannakiran2001-beep/MediaDNA
- **Default admin:** set via `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`

## AI providers & models used
| Purpose | Provider / Model | Notes |
|---|---|---|
| Orchestration + provenance | **Genblaze SDK** (`genblaze`, `genblaze-core`, `genblaze-s3`) | Real `Pipeline` → verified `Manifest` (canonical SHA-256) |
| Image generation | **Pollinations FLUX** (keyless) | Free text-to-image; swap in GMICloud/OpenAI/Stability by setting that provider's key |
| Captioning / object labels | Prompt-derived (generated assets) | The prompt is the ground-truth description — accurate, no paid model |
| OCR | **Tesseract** (open-source) | Real text extraction from images/documents |
| Colour / style / quality | Local (Pillow + NumPy) | Dominant colours (k-means), style inference, Laplacian sharpness |
| Embeddings / semantic search | Local hashing embedding (384-d) | Lightweight, free; pgvector-ready for production |

> Configurable: set `HF_TOKEN` or a sponsor provider key (GMICloud/OpenAI/Stability/Runway/Luma) to
> upgrade captioning, detection, and video generation — the pipeline code is unchanged.

## How we use Backblaze B2
- All artifacts are stored in B2 via the official **`genblaze_s3.S3StorageBackend.for_backblaze(...)`**:
  **originals, thumbnails, embeddings, and provenance manifests**.
- Delivery uses **short-lived signed URLs** (`presigned_get_url`) — B2 credentials never reach the
  browser; the API signs and redirects, B2 serves the bytes.
- Region auto-detection and pooled connections make it resilient on free hosting.

## How we use Genblaze
- Generation runs through a real **`genblaze.Pipeline().step(provider, ...).run()`**.
- Every run emits a hash-verified **`Manifest`** (`manifest.verify() == True`) stored in the asset's
  DNA and in B2 — this is the tamper-evident provenance record.
- Custom `SyncProvider` wraps the image generator behind the Genblaze contract, so swapping to any
  sponsor provider is a one-line change.

## 3-minute demo script
1. **(0:00) Landing** — open `/`: the problem (`file_final_v3_real_final.png`), the pipeline, the pitch.
2. **(0:25) Sign in** — email one-time code (dev mode shows it in-app) → dashboard.
3. **(0:45) Generate** — Generate tab → prompt "cyberpunk city street at night, neon, rain" → watch
   the Genblaze pipeline run → a real image appears with a **✓ verified provenance manifest**.
4. **(1:20) DNA record** — open the asset: prompt, model, provider, colours, OCR, checksum, manifest
   hash, storage backend = **b2**.
5. **(1:45) Fork & region edit** — Fork to regenerate a variation; then "Edit region", drag a box,
   type a change → a new version is created and linked.
6. **(2:20) Lineage graph** — show the auto-built graph connecting the original, forks, and edits.
7. **(2:40) Semantic search** — "cyberpunk images" → ranked results; open one; show it's stored in B2.
8. **(2:55) Admin** — approvals + user roles. Close on the verified-manifest badge.

## Judging-criteria mapping
- **Real-World Utility** — solves AI-asset chaos: provenance, lineage, versioning, search, approvals.
- **Production Readiness** — clean architecture (repository/service layers), auth + admin, Docker,
  Supabase Postgres, health checks, signed-URL delivery.
- **B2 Storage & Orchestration** — official `genblaze_s3` backend; multiple artifact types; signed URLs.
- **Use of Genblaze** — real Pipeline + verified Manifest on every generation.
