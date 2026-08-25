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

    _origins = os.environ.get("CORS_ORIGINS", "*")
    CORS_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()] or ["*"]

    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("FLASK_DEBUG", "true").strip().lower() in ("1", "true", "yes")

    @staticmethod
    def validate():
        if not Config.MONGODB_URI:
            raise RuntimeError(
                "MONGODB_URI is not set. Copy .env.example to .env at the project "
                "root and fill in your MongoDB connection string."
            )
