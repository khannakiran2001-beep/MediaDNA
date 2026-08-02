# MediaDNA — single container serving the API + SPA.
# Works on Render, Railway, Fly.io, Hugging Face Spaces, or any Docker host.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Tesseract for free, real OCR (open-source).
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# System deps for Pillow/numpy wheels are already bundled; keep image slim.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Writable data dir (SQLite/CA-bundle fallback); on HF Spaces / read-only hosts
# the app also falls back to /tmp automatically and uses Supabase + B2 in prod.
RUN mkdir -p /app/backend/data/storage && chmod -R 777 /app/backend/data

WORKDIR /app/backend
EXPOSE 8000
# $PORT is provided by most PaaS hosts; default to 8000 locally.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
