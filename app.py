"""Flask application entry point."""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from config import Config
from extensions import db


def _try_postgres(uri):
    """Return True if we can actually connect to the given Postgres URI."""
    try:
        engine = create_engine(uri, pool_pre_ping=True)
        with engine.connect() as _:
            pass
        engine.dispose()
        return True
    except Exception:
        return False


def _resolve_database_uri():
    """Pick the database to use: prefer configured Postgres, fall back to SQLite."""
    primary = Config.SQLALCHEMY_DATABASE_URI
    explicit = os.getenv("DATABASE_URL")

    # If user explicitly set DATABASE_URL, respect it without fallback magic
    if explicit:
        return primary, "user-configured (DATABASE_URL)"

    # Default Postgres path — try, but fall back if not available
    if primary.startswith("postgresql"):
        if _try_postgres(primary):
            return primary, "Postgres (default)"
        # Fall back to SQLite for first-time / minimal local testing
        os.makedirs(Config.INSTANCE_DIR, exist_ok=True)
        return Config.SQLITE_FALLBACK_URI, "SQLite (Postgres unreachable, using fallback)"

    return primary, "configured"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Resolve DB at boot (with Postgres → SQLite fallback)
    resolved_uri, db_source = _resolve_database_uri()
    app.config["SQLALCHEMY_DATABASE_URI"] = resolved_uri
    app.config["DB_SOURCE"] = db_source
    print(f"[glam-nails] DB: {db_source} → {resolved_uri.split('@')[-1]}")

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    db.init_app(app)

    # Register blueprints
    from routes.public import bp as public_bp
    from routes.admin import bp as admin_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def root():
        return jsonify({
            "name": app.config["SITE_NAME"],
            "status": "ok",
            "db": app.config["DB_SOURCE"],
            "api": "/api",
        })

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "db": app.config["DB_SOURCE"]})

    # Initialize the database + seed on startup if empty
    with app.app_context():
        db.create_all()
        from seed import seed_if_empty
        seed_if_empty()

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
