# 🎬 MediaDNA — Demo Storyboard

A shot-by-shot storyboard for the 3-minute hackathon demo. Everything in one place: timing,
what's on screen, the exact action, the narration (for live read or AI TTS), and the on-screen
caption. Total ≈ **2:50**.

> **Before recording:** open the app, sign in as **admin**, and generate/seed 3–4 assets so the
> graph and search look full. Record at 1080p (Win+G or OBS).

---

## Shot list (overview)

| # | Time | Scene | On screen | Caption |
|---|------|-------|-----------|---------|
| 1 | 0:00–0:18 | Title + problem | Title card → landing page | *MediaDNA — GitHub for AI Assets* |
| 2 | 0:18–0:30 | Sign in | Auth screen → dashboard | *Secure auth — email OTP + password* |
| 3 | 0:30–1:00 | Generate | Generate tab, pipeline runs | *Real Genblaze pipeline → verified provenance* |
| 4 | 1:00–1:30 | DNA record | Asset modal (manifest, B2) | *Full DNA — prompt, checksum, verified manifest* |
| 5 | 1:30–2:00 | Fork + region edit | Fork; drag-select region | *Version control for images* |
| 6 | 2:00–2:25 | Graph + search | Lineage graph → search | *Auto lineage graph + semantic search* |
| 7 | 2:25–2:40 | Admin | Admin panel | *Team-ready — roles, approvals, audit* |
| 8 | 2:40–2:50 | Outro | Outro card | *Built on Genblaze + Backblaze B2* |

---

## Scene 1 — Title + the problem · `0:00–0:18`
- **Screen:** open `docs/video-titlecard.html` full-screen (~4s), then the landing page at `/`; scroll past the `file_final_v3_real_final.png` problem panel and the pipeline diagram; click **Launch app**.
- **🎙️ Narration:** "Developers have Git. Designers have Figma. AI-generated media has nothing. The moment an image is made, its context is lost. MediaDNA fixes that."
- **💬 Caption:** MediaDNA — GitHub for AI Assets

## Scene 2 — Sign in · `0:18–0:30`
- **Screen:** the sign-in screen; log in with the admin email + password → dashboard.
- **🎙️ Narration:** "Sign in is email and password, with email verification on sign-up and a forgot-password flow built in."
- **💬 Caption:** Secure auth — email OTP + password

## Scene 3 — Generate with Genblaze · `0:30–1:00`
- **Screen:** Generate tab → type *"a cyberpunk city street at night, neon signs, rain, cinematic"* → **Generate**; let the pipeline status animate and the image appear.
- **🎙️ Narration:** "Let's make an asset. This runs a real Genblaze pipeline. Every generation produces a cryptographically verified provenance manifest, and every file is stored in Backblaze B2."
- **💬 Caption:** Real Genblaze pipeline → verified provenance

## Scene 4 — The DNA record · `1:00–1:30`
- **Screen:** click the new asset → DNA modal. **Linger** on the ⛓️ *verified manifest* card, the dominant-colour swatches, and the **storage: b2** row in the full DNA record.
- **🎙️ Narration:** "Here's its DNA: the prompt, model, provider, colours, OCR, and checksum — plus a Genblaze manifest marked verified and stored in B2. The image is delivered through a signed URL, so credentials never reach the browser."
- **💬 Caption:** Full DNA — prompt, checksum, verified manifest, B2

## Scene 5 — Fork + region edit · `1:30–2:00`
- **Screen:** click **Fork / Regenerate**, enter *"…at sunset, orange sky"*, show the new version appear. Reopen an asset → **Edit region** → drag a box → type *"a full moon"* → submit.
- **🎙️ Narration:** "Like Git, any asset can branch. Fork regenerates a brand-new variation, linked as a child version. Or select a region and regenerate only that part."
- **💬 Caption:** Version control for images — fork & region edit

## Scene 6 — Lineage graph + search · `2:00–2:25`
- **Screen:** open **Lineage Graph** (show clusters, click a node → its DNA). Then **Search** → type *"cyberpunk"* → ranked results.
- **🎙️ Narration:** "Everything connects. The lineage graph builds itself from forks, edits, and duplicates. And search is semantic — just ask in plain language."
- **💬 Caption:** Auto lineage graph + semantic search

## Scene 7 — Admin · `2:25–2:40`
- **Screen:** open **Admin** → approve a pending asset → toggle a user's role.
- **🎙️ Narration:** "For teams, an admin panel with roles, an approval workflow, and audit logs on everything."
- **💬 Caption:** Team-ready — roles, approvals, audit logs

## Scene 8 — Outro · `2:40–2:50`
- **Screen:** `docs/video-titlecard.html` → click **Show outro variant**.
- **🎙️ Narration:** "MediaDNA — permanent identity, complete lineage, and verified provenance for every AI asset. Built on Genblaze and Backblaze B2."
- **💬 Caption:** MediaDNA · Built on Genblaze + Backblaze B2

---

### Produce it (all free)
1. **Voiceover:** paste each 🎙️ line into a free TTS (ElevenLabs / Edge Read Aloud / Play.ht) → export clips.
2. **Record:** Win+G or OBS, click through scenes 1–8.
3. **Assemble:** CapCut / Canva — footage + voiceover + captions + title card, trim ≤ 3:00, export.
4. Upload (YouTube unlisted / Devpost) and paste the link into the submission.
