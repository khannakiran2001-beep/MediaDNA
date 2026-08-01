---
title: MediaDNA
emoji: 🧬
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
short_description: GitHub for AI Assets — provenance, lineage & search on B2
---

# MediaDNA — GitHub for AI Assets 🧬

> The block above is Hugging Face Space configuration. On any other host it's just metadata — ignore it.

Every AI-generated asset gets a **permanent identity, complete lineage, and searchable history**.
Instead of storing files, MediaDNA stores *knowledge about files* — a DNA record for every image,
video, audio clip, or document.

This repo is a **runnable MVP**: FastAPI + SQLite + a polished dark-mode SPA, with a modular
**Genblaze** AI pipeline and pluggable **Backblaze B2** storage. It runs fully offline with
deterministic fallbacks, and upgrades to live **Hugging Face** models + **B2** the moment you add
credentials.

## Quick start

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# (optional) seed demo assets + lineage:
cd ..
python scripts/seed.py

# run:
cd backend
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**.

## What works

| Area | Implementation |
|------|----------------|
| **Genblaze SDK (real)** | Generation runs through an actual `genblaze.Pipeline` with a custom `SyncProvider`, producing a cryptographically **verified provenance `Manifest`** (canonical SHA-256) per asset (`app/services/genblaze_runner.py`) |
| **Backblaze B2 (real SDK)** | Storage routes through the official `genblaze_s3.S3StorageBackend.for_backblaze(...)` when B2 creds are set; a local genblaze `StorageBackend` otherwise. Credentials never reach the client — bytes stream through the API (`app/services/storage.py`) |
| **Analysis pipeline** | Modular stages on the generated/uploaded bytes: metadata → caption → object detection → colour/style/quality → embedding (`app/services/pipeline.py`) |
| **AI providers** | `AIProvider` → `HuggingFaceProvider` (BLIP caption, DETR detection, MiniLM embeddings) with a deterministic `LocalHeuristicProvider` fallback; image generation via HF → Pollinations (keyless FLUX) → procedural |
| **DNA record** | Full provenance, checksum, colours, objects, embedding, versions, approval, downloads, comments, audit logs |
| **Lineage graph** | Auto-detected relationships (duplicate / near-duplicate / fork / edit) rendered with Cytoscape |
| **Semantic search** | Embedding cosine + keyword + metadata filters (provider/model/project/tag) |
| **Version control** | Fork creates a child version sharing a root; version history per asset |
| **UI** | Dashboard, asset grid, asset DNA modal, graph, collections, activity, ⌘K command palette, keyboard shortcuts |

## Enabling live integrations

Copy `backend/.env.example` → `backend/.env` and fill in:

- `HF_TOKEN` — enables real Hugging Face captioning/detection/embeddings.
- `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET_NAME` — enables Backblaze B2 storage.

Sidebar badges show which integrations are **live** vs **fallback**.

## Architecture

```
backend/app
  config.py          settings (env-driven, optional integrations)
  database.py        SQLAlchemy engine/session (SQLite → Postgres/pgvector ready)
  models.py          Asset, Relationship, Comment, AuditLog, Collection
  repositories.py    repository pattern (all DB access)
  schemas.py         Pydantic I/O
  services/
    providers.py     AIProvider / HuggingFaceProvider / LocalHeuristicProvider
    pipeline.py      Genblaze orchestration (modular stages)
    storage.py       StorageProvider / B2Storage / LocalStorage
    search.py        semantic search + relationship detection
    asset_service.py use-cases (ingest, fork, version)
  main.py            FastAPI app + routes + serves the SPA
frontend/            index.html + app.js (Tailwind CDN + Cytoscape)
scripts/seed.py      demo data generator
```

## Authentication

Email-OTP auth with a password option and an admin role:

- **Register** → email + name → 6-digit code (dev mode surfaces the code in-app when SMTP is unset).
- **Sign in** → password *or* one-time email code.
- **Default admin** is auto-created on startup: `admin@mediadna.app` / `MediaDNA!Admin2026`
  (override via `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD` — **change these in production**).
- First self-registered user becomes admin when `ADMIN_EMAILS` is unset.
- **Admin panel**: manage user roles, activate/deactivate users, approve/reject assets.

## Supabase (Postgres) database

Set `DATABASE_URL` to your Supabase connection string (the driver `psycopg` is included):

```
DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

Tables are auto-created on first boot. (Embeddings are stored as JSON today; a
`pgvector` column is the production upgrade — Supabase supports the extension.)

## Deployment

### Hugging Face Spaces (Docker) — free, no card ⭐

The root `README.md` already carries the Space config header (`sdk: docker`, `app_port: 8000`)
and the root `Dockerfile` builds the app.

1. Create free accounts: **Supabase** (Postgres) and confirm your **Backblaze B2** bucket.
2. On huggingface.co → **New Space** → **Docker** (blank template) → name it `mediadna`.
3. Push this repo to the Space:
   ```bash
   git init && git add . && git commit -m "MediaDNA"
   git remote add space https://huggingface.co/spaces/<your-username>/mediadna
   git push space main
   ```
4. In the Space → **Settings → Variables and secrets**, add (as *secrets*):
   `DATABASE_URL` (Supabase), `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET_NAME`, `B2_REGION`,
   `SECRET_KEY`, `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD` (and optional `HF_TOKEN`, `SMTP_*`).
5. The Space builds the Dockerfile and serves on `app_port` 8000. Sign in with your admin creds.

> `.env` and `backend/data/` are git-ignored, so secrets are never pushed — set them in the Space UI.

### Alternative Docker hosts (Render / Railway / Fly.io) — reliable free tiers
The app is a long-running ASGI server that serves both the API and the SPA. A `Dockerfile`
and `render.yaml` are included.

1. Create a **Supabase** project → copy the Postgres `DATABASE_URL`.
2. Create a **Backblaze B2** bucket → key id / app key / region.
3. Push to GitHub, then on Render: *New → Blueprint* (uses `render.yaml`), or *New → Web Service → Docker*.
4. Set env vars: `DATABASE_URL`, `B2_*`, `SECRET_KEY`, `DEFAULT_ADMIN_*`, optional `SMTP_*`.

### Vercel — possible, with caveats
`vercel.json` + `api/index.py` are included to run the FastAPI app on Vercel's Python runtime.
It **requires** `DATABASE_URL` (Supabase) and `B2_*` because Vercel's filesystem is read-only
(no SQLite, no local storage). Caveats on the free/Hobby plan: 60s function limit (image
generation usually fits) and a 250 MB bundle limit that the heavy deps (boto3 + numpy + pillow +
genblaze) may bump against. If a deploy fails on size or cold-starts, use the Docker option above.

> Note: **v0** (v0.dev) is Vercel's AI *frontend* generator — it doesn't host this Python backend.
> "Deploy on Vercel" means the Vercel platform, configured as above.

## Production upgrade path

- Swap `DATABASE_URL` to PostgreSQL and move `embedding` to a `pgvector` column.
- Move the pipeline into Celery workers (Redis broker) — stages are already isolated functions.
- Replace the SPA with the Next.js 15 / shadcn frontend; the JSON API is unchanged.
- Add Clerk auth middleware in front of the API.
