"""
Vercel serverless entrypoint.

Vercel's Python runtime treats any file under /api as a serverless
function and looks for a WSGI-compatible `app` object in it. This file
does nothing but re-expose the existing Flask app from backend/app.py —
all routes, validation, and MongoDB access stay exactly where they were
and are unchanged. vercel.json rewrites every /api/* request to this
one function; Flask's own blueprint routing (registered with url_prefix
like /api/products) handles the rest, exactly as it does when the app
is run locally via `python -m backend.app`.
"""
import sys
from pathlib import Path

# Vercel invokes this file directly, which puts only api/ on sys.path.
# Add the project root so `import backend...` resolves the same way it
# does locally when run as `python -m backend.app` from the root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import app  # noqa: E402  (import after sys.path setup, by design)
