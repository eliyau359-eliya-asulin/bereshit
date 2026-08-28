"""
Configuration loaded from environment variables (.env at the project root).
No secrets are hardcoded here — see ../.env.example for the expected shape.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # project root (one level above backend/)
load_dotenv(BASE_DIR / ".env")


class Config:
    MONGODB_URI = os.environ.get("MONGODB_URI")
    # Only used as a fallback if MONGODB_URI doesn't already specify a database
    # (e.g. ".../Bereshit" in the URI path takes precedence).
    MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "bereshit")

    # No wildcard default: cookies (Authorization-by-session) require the
    # browser to see an explicit origin, and flask-cors + supports_credentials
    # refuses to combine "*" with credentials anyway. Same-origin production
    # deployments (Vercel serving both the static site and /api/*) don't need
    # this at all; it only matters for cross-port local dev.
    _origins = os.environ.get("CORS_ORIGINS", "http://localhost:8123,http://127.0.0.1:8123")
    CORS_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]

    PORT = int(os.environ.get("PORT", 5000))
    # Defaults to OFF. Debug mode executes arbitrary code via the Werkzeug
    # debugger and leaks stack traces to the client — never appropriate in
    # production. Must be explicitly opted into for local development.
    DEBUG = os.environ.get("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")

    # Session cookies default to Secure (HTTPS-only). Set to "false" only for
    # local development over plain http:// — never in a deployed environment.
    COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").strip().lower() in ("1", "true", "yes")

    # First super-admin account, created once at startup if backend.admin_users
    # is empty. Not set = no admin account exists yet and admin login is
    # unusable until one is created directly in the database or these vars
    # are provided — intentionally, so no default/placeholder credential is
    # ever shipped.
    ADMIN_BOOTSTRAP_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL")
    ADMIN_BOOTSTRAP_PASSWORD = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
    ADMIN_BOOTSTRAP_NAME = os.environ.get("ADMIN_BOOTSTRAP_NAME", "Super Admin")

    @staticmethod
    def validate():
        if not Config.MONGODB_URI:
            raise RuntimeError(
                "MONGODB_URI is not set. Copy .env.example to .env at the project "
                "root and fill in your MongoDB connection string."
            )
