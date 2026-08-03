# MediaDNA — Devpost Submission

**Tagline:** GitHub for AI Assets — permanent identity, complete lineage, and verified provenance for every AI-generated image, video, audio, and document.

**Try it:** `https://<your-service>.onrender.com` · **Code:** https://github.com/khannakiran2001-beep/MediaDNA

---

## 💡 Inspiration
Developers have Git. Designers have Figma. **AI-generated media has nothing.**

The moment a team generates an image, the context evaporates. Which prompt made it? Which model and provider? Which version is newest? Which campaign used it? Who approved it? What did it evolve from? Weeks later the file is `campaign_final_v3_real_FINAL.png` sitting in a Drive folder, and nobody can answer any of those questions.

Companies now generate **thousands of AI assets a month**. We wanted the operating system for that content — a place that doesn't just store files, but stores *knowledge about files*. That's MediaDNA.

## 🧬 What it does
Every asset in MediaDNA gets a **DNA record** and a place in a living lineage graph:

- **Generate or upload** an image/video/audio/doc → a modular pipeline analyzes it and produces a verified provenance record.
- **DNA record:** original prompt, model, provider, generation parameters, checksum, dominant colours, visual style, quality score, OCR text, object labels, embedding, thumbnail, approvals, comments, and audit history.
- **Version control like Git:** fork any asset to regenerate a new variation, or select a region and regenerate just that part — each becomes a linked child version.
- **Lineage graph:** relationships (forked, edited, duplicate, related) are detected automatically and rendered as an interactive graph.
- **Semantic search:** ask in plain language ("cyberpunk images from the summer campaign") — embeddings + metadata + keyword filters.
- **Team-ready:** email-OTP + password auth, an admin panel with roles, an asset approval workflow, and audit logs.

## 🏗️ How we built it
- **Genblaze SDK (real orchestration + provenance).** Generation runs through an actual `genblaze.Pipeline().step(provider, …).run()`. A custom `SyncProvider` wraps the image generator behind the Genblaze contract, and every run emits a hash-verified `Manifest` (`manifest.verify() == True`) — a canonical SHA-256 over the run that becomes the tamper-evident provenance record.
- **Backblaze B2 (durable storage + data orchestration).** All artifacts — originals, thumbnails, embeddings, and provenance manifests — are stored in B2 through the official `genblaze_s3.S3StorageBackend.for_backblaze(...)`. Delivery uses **short-lived signed URLs**: the API signs and redirects, B2 serves the bytes, and credentials never touch the client. We added automatic region resolution and pooled connections so it's resilient on free hosting.
- **Backend:** FastAPI with clean architecture — repository + service layers, dependency injection, Pydantic schemas, comprehensive logging and error handling. PostgreSQL (Supabase) via SQLAlchemy; pgvector-ready.
- **Frontend:** a dark-mode single-page app (GitHub/Linear-inspired) with a command palette, keyboard shortcuts, the interactive lineage graph, and a drag-to-select region editor.
- **AI analysis (free):** captions/object labels derived from the prompt for generated assets, real OCR via Tesseract, dominant-colour/style/quality from the pixels, and embeddings that combine prompt + caption + OCR for semantic search. Image generation uses the keyless Pollinations FLUX endpoint — swap in GMICloud/OpenAI/Stability by setting that provider's key; the pipeline code is unchanged.
- **Deploy:** Dockerized; runs on Render / Hugging Face Spaces / Fly, with Supabase for Postgres and B2 for storage — a fully free stack.

## 🧗 Challenges we ran into
- **Provenance that actually verifies.** Wiring generation through a real Genblaze `Pipeline` (not a namesake) so every asset carries a cryptographically verified `Manifest`.
- **Serving from B2 without leaking credentials — or stalling.** Proxying every read through the app exhausted the S3 client's connection pool. We switched to **presigned URLs** (the "Signed URLs" pattern), which offloads delivery to B2 and fixed it.
- **Free hosting networking.** Supabase's direct connection is IPv6-only and Render's free tier is IPv4-only; we moved to the Supavisor **session pooler**. We also auto-rewrite `postgres://` → `postgresql+psycopg://` so the modern driver is used, and auto-detect the bucket region.
- **The moving AI free-tier landscape.** Hugging Face's free serverless dropped the caption/detection models and Pollinations' vision endpoint began charging mid-build — so we kept analysis accurate and free by deriving it from the prompt and using open-source Tesseract for OCR.

## 🏆 Accomplishments we're proud of
- A **verified provenance manifest on every generation**, stored durably in B2.
- **Fork-to-regenerate** and **region editing** that make versioning feel like Git for images.
- A genuinely **free, end-to-end stack** (generation, storage, DB, hosting) that still uses the real sponsor tech.
- A polished, production-shaped codebase: auth (register/login/forgot-password), admin + approvals, rate limiting, health checks, and a 33-check end-to-end test suite that passes.

## 📚 What we learned
- Provenance is a *product feature*, not plumbing — a visible "verified" badge changes how people trust an asset.
- Signed URLs are the right way to serve object storage: faster, safer, and they keep credentials server-side.
- Design for pluggability: because generation and analysis sit behind clean provider interfaces, upgrading to a paid vision/video model is a one-line change.

## 🔭 What's next
- Real multimodal generation (video/audio) via GMICloud/Runway/Luma once keys are available.
- pgvector-backed vector search at scale.
- B2 Object Lock for immutable, tamper-proof provenance.
- Deeper Genblaze multi-step chained pipelines (image → upscale → video).

## 🛠️ Built With
`genblaze` · `backblaze-b2` · `python` · `fastapi` · `sqlalchemy` · `postgresql` · `supabase` · `pgvector` · `tesseract` · `pollinations-flux` · `docker` · `render` · `javascript` · `tailwindcss` · `cytoscape.js`
