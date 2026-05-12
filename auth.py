"""Admin authentication helpers."""
from datetime import datetime, timedelta
from functools import wraps
import jwt
from flask import current_app, request, jsonify


def make_admin_token():
    """Create a JWT for an admin session lasting 7 days."""
    payload = {
        "sub": "admin",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def verify_admin_token(token):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload.get("sub") == "admin"
    except jwt.PyJWTError:
        return False


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth.split(" ", 1)[1].strip()
        if not verify_admin_token(token):
            return jsonify({"error": "Invalid or expired session"}), 401
        return fn(*args, **kwargs)

    return wrapper
