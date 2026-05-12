"""Configuration: loads config.json for branding/persona,
and merges environment variables for secrets (DATABASE_URL, ADMIN_PASSWORD, etc.)."""
import json
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_JSON_PATH = os.path.join(BASE_DIR, "config.json")


def _load_config_json():
    """Load the swappable persona/branding config. Fail loudly if missing."""
    if not os.path.exists(CONFIG_JSON_PATH):
        raise RuntimeError(
            f"config.json not found at {CONFIG_JSON_PATH}. "
            "It ships with the project — restore it from the original archive."
        )
    with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_CFG = _load_config_json()


class Config:
    # ─── Secrets / infrastructure (from .env) ─────────────────────────────
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "glam2026")

    # Database — defaults to Postgres on localhost (matches prod stack).
    # If Postgres isn't reachable on boot, app.py falls back to SQLite.
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Default: local Postgres database named "glamnails"
        SQLALCHEMY_DATABASE_URI = "postgresql://localhost/glamnails"

    # SQLite fallback URI (used by app.py if Postgres connection fails on boot)
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    SQLITE_FALLBACK_URI = f"sqlite:///{os.path.join(INSTANCE_DIR, 'glam.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    CORS_ORIGINS = [
        o.strip() for o in os.getenv(
            "CORS_ORIGINS", _CFG["messaging"]["frontend_base_url"]
        ).split(",") if o.strip()
    ]

    # ─── Persona / branding (from config.json) ────────────────────────────
    SITE_CONFIG = _CFG  # full dict — passed through to /api/site

    SITE_NAME = _CFG["site"]["name"]
    SITE_CITY = _CFG["site"]["city"]
    NAIL_TECH_NAME = _CFG["tech"]["name"]
    NAIL_TECH_PHONE = _CFG["tech"]["phone"]

    TIMEZONE = _CFG["operations"]["timezone"]
    LEAD_TIME_MINUTES = int(_CFG["operations"].get("lead_time_minutes", 30))
    FRONTEND_BASE_URL = _CFG["messaging"]["frontend_base_url"]
