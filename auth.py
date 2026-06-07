"""
auth.py — Session-based JWT auth layer
Role decorators: @login_required, @role_required('teacher'), etc.
JWT payload stored in session cookie — HttpOnly, SameSite=Lax.
"""

import jwt
import os
from functools import wraps
from datetime import datetime, timedelta
from flask import request, jsonify, session

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
TOKEN_EXPIRY_HOURS = 24


def generate_token(user: dict) -> str:
    """Generate a JWT for the given user."""
    payload = {
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns payload or None."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    """
    Extract current user from Authorization header (Bearer token).
    Returns decoded payload dict or None.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return decode_token(token)


def login_required(f):
    """Decorator: requires valid JWT in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "status": "error",
                "message": "Authentication required. Please log in."
            }), 401
        return f(*args, **kwargs, current_user=user)
    return decorated


def role_required(*roles):
    """
    Decorator: requires valid JWT AND specific role(s).
    Usage: @role_required('teacher') or @role_required('teacher', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({
                    "status": "error",
                    "message": "Authentication required."
                }), 401
            if user["role"] not in roles:
                return jsonify({
                    "status": "error",
                    "message": f"Access denied. Required role: {' or '.join(roles)}."
                }), 403
            return f(*args, **kwargs, current_user=user)
        return decorated
    return decorator
