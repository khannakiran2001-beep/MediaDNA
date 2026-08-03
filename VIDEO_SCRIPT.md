# MediaDNA — 3-Minute Demo Video Script

**Goal:** hit all four judging criteria — Real-World Utility, Production Readiness,
B2 Storage & Orchestration, Use of Genblaze.

**Setup before recording**
- Open the deployed app (or `http://localhost:8000`). Make sure a few assets already
  exist so the graph/search look populated (run `python scripts/seed.py`, or generate 3–4).
- Be **logged in as admin** so you can show the admin panel.
- Record at 1920×1080. Keep the browser clean (hide bookmarks bar).
- Tools: **OBS Studio** (free) or Windows **Win+G** Game Bar, or **Loom** free. Add voiceover
  live, or record silent and narrate after. For narration you can read the lines below or paste
  them into a free TTS.

Total target: **~3:00**. Timecodes are cumulative.

---

### 0:00–0:20 · Title + the problem
**On screen:** Title card (`docs/video-titlecard.html`), then the landing page at `/`.
**Narration:**
> "Developers have Git. Designers have Figma. AI-generated media has… nothing. The moment an
> image is made, the context is lost — the prompt, the model, the version, who approved it.
> This is MediaDNA: GitHub for AI assets."

**Action:** scroll the landing page past the `file_final_v3_real_final.png` problem panel and the
Genblaze pipeline diagram. Click **Launch app**.

### 0:20–0:35 · Sign in (auth)
**On screen:** the sign-in screen.
**Narration:**
> "Sign in is email plus password, with email-OTP verification on registration and a
> forgot-password flow — all built in."

**Action:** log in with your admin email + password → dashboard appears.

### 0:35–1:05 · Generate with Genblaze (the core)
**On screen:** Generate tab.
**Narration:**
> "Let's create an asset. This runs a real Genblaze Pipeline — not a mock. Each generation
> produces a cryptographically verified provenance manifest, and every artifact lands in
> Backblaze B2."

**Action:** Generate tab → type *"a cyberpunk city street at night, neon signs, rain, cinematic"*
→ click **Generate**. Let the pipeline status animate and the image appear in "This session".

### 1:05–1:35 · The DNA record (utility + B2 + Genblaze)
**On screen:** click the new asset → DNA modal.
**Narration:**
> "Here's its DNA: the prompt, model, provider, dominant colours, OCR, checksum — and a
> Genblaze provenance manifest marked verified, stored durably in B2. The image itself is
> delivered through a short-lived signed URL, so credentials never touch the browser."

**Action:** point out the **⛓️ verified manifest** card, dominant colours, and the "storage: b2"
row in the full DNA record.

### 1:35–2:05 · Fork & region edit (versioning)
**On screen:** still in the modal.
**Narration:**
> "Like Git, any asset can branch. Fork regenerates a new variation — a real new image, linked
> as a child version. Or select a region and regenerate just that part."

**Action:** click **Fork / Regenerate**, enter *"…at sunset, orange sky"*, show the new version
appear. Reopen an asset, click **Edit region**, drag a box, type *"a full moon"*, submit.

### 2:05–2:30 · Lineage graph + search
**On screen:** Lineage Graph tab, then Search tab.
**Narration:**
> "Everything is connected. The lineage graph auto-builds relationships — forks, edits,
> duplicates. And search is semantic: ask in plain language."

**Action:** open **Lineage Graph** (show clusters, click a node). Then **Search** → type
*"cyberpunk"* → show ranked results.

### 2:30–2:50 · Admin (production readiness)
**On screen:** Admin tab.
**Narration:**
> "For teams: an admin panel with roles, user management, and an approval workflow — plus audit
> logs on everything."

**Action:** open **Admin**, approve a pending asset, toggle a user role.

### 2:50–3:00 · Close
**On screen:** outro title card.
**Narration:**
> "MediaDNA — permanent identity, complete lineage, and verified provenance for every AI asset.
> Built on Genblaze and Backblaze B2."

---

## Narration (continuous, for TTS)
> Developers have Git. Designers have Figma. AI-generated media has nothing. The moment an image
> is made, the context is lost — the prompt, the model, the version, who approved it. This is
> MediaDNA: GitHub for AI assets. Sign in is email plus password, with email-OTP verification and
> a forgot-password flow. Let's create an asset. This runs a real Genblaze Pipeline — each
> generation produces a cryptographically verified provenance manifest, and every artifact lands
> in Backblaze B2. Here's its DNA: prompt, model, provider, colours, OCR, checksum — and a
> Genblaze manifest marked verified, stored in B2, delivered through short-lived signed URLs.
> Like Git, any asset can branch: fork regenerates a new variation, or select a region and
> regenerate just that part. Everything is connected — the lineage graph auto-builds
> relationships, and search is semantic. For teams, an admin panel with roles and an approval
> workflow. MediaDNA — permanent identity, complete lineage, and verified provenance for every AI
> asset. Built on Genblaze and Backblaze B2.

## Recording checklist
- [ ] Seed/generate a few assets first so graph + search look full
- [ ] Logged in as admin
- [ ] 1080p, clean browser
- [ ] One take following the timecodes; re-record any fumbled section
- [ ] Add the title card at the start and outro at the end
- [ ] Export ≤ 3:00, upload (YouTube unlisted / Devpost), paste the link in the submission
