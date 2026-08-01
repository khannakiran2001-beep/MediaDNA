"""Vercel Python entrypoint.

Exposes the FastAPI app as a serverless function. All routes are rewritten to
this file via vercel.json. Requires DATABASE_URL (Supabase Postgres) and B2
credentials as environment variables — the serverless filesystem is read-only,
so SQLite/local storage are not usable in this deployment target.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: E402

# Vercel's @vercel/python runtime detects the ASGI `app` object automatically.
