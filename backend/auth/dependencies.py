"""
FastAPI dependencies for authentication and role-based access control.

Used as Depends(...) in route handlers to enforce admin or super-admin access.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, Request

from database import users_col


def get_bearer(request: Request) -> str:
    """Extract the Bearer token from the Authorization header."""
    return request.headers.get("Authorization", "").removeprefix("Bearer ").strip()


def verify_token(token: str) -> dict | None:
    """
    Return user doc if token is valid, not expired, and the user is active.
    Returns None otherwise.
    """
    if not token:
        return None
    user = users_col.find_one({"active_token": token})
    if not user:
        return None
    if not user.get("active", True):
        return None
    exp = user.get("token_expires_at")
    if not exp:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        return None
    return user


def require_admin(request: Request) -> dict:
    """FastAPI dependency — allows any authenticated admin user (any role)."""
    token = get_bearer(request)
    user  = verify_token(token)
    if not user:
        raise HTTPException(401, "Admin authentication required")
    return user


def require_super_admin(request: Request) -> dict:
    """FastAPI dependency — allows only SUPER_ADMIN role."""
    token = get_bearer(request)
    user  = verify_token(token)
    if not user:
        raise HTTPException(401, "Admin authentication required")
    if user.get("role") != "SUPER_ADMIN":
        raise HTTPException(403, "This action requires SUPER_ADMIN privileges")
    return user
