"""
Admin user management routes — SUPER_ADMIN only.

List, create, edit, and activate/deactivate admin portal users.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import DESCENDING

from auth import require_super_admin
from config import tq, tenant, user_email
from database import users_col
from models import UserCreateIn, UserUpdateIn

router = APIRouter(prefix="/api/admin/users", tags=["Admin Users"])


@router.get("")
def list_admin_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _admin: dict = Depends(require_super_admin),
):
    """Return admin users for this tenant (passwords excluded)."""
    q = tq()
    if role:
        q["role"] = role
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    projection = {"password_hash": 0, "active_token": 0, "token_expires_at": 0, "totp_secret": 0}

    def _fmt_user(d):
        d["id"] = str(d.pop("_id"))
        ca = d.get("created_at")
        if isinstance(ca, datetime):
            d["created_at"] = ca.isoformat()
        return d

    cursor = users_col.find(q, projection).sort("created_at", DESCENDING)
    if page is not None:
        page = max(1, page)
        total = users_col.count_documents(q)
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        items = [_fmt_user(d) for d in cursor]
        return {"total": total, "page": page, "limit": limit, "items": items}
    return [_fmt_user(d) for d in cursor]


@router.post("", status_code=201)
def create_admin_user(body: UserCreateIn, _admin: dict = Depends(require_super_admin)):
    """Create a new admin user scoped to the current tenant."""
    existing = users_col.find_one(tq({"email": body.email}))
    if existing:
        raise HTTPException(409, "A user with that email already exists")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(body.password.encode(), salt).decode()
    doc = {
        "tenant_name":   tenant(),
        "email":         body.email,
        "name":          body.name,
        "password_hash": hashed,
        "role":          body.role or "ADMIN",
        "active":        True,
        "created_at":    datetime.now(timezone.utc),
        "created_by":    user_email(),
    }
    result = users_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{user_id}/status")
def toggle_admin_user_status(user_id: str, _admin: dict = Depends(require_super_admin)):
    """Toggle active flag. SUPER_ADMIN cannot deactivate themselves."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    user = users_col.find_one(tq({"_id": oid}))
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("email") == _admin.get("email"):
        raise HTTPException(400, "You cannot deactivate your own account")
    new_active = not user.get("active", True)
    update: dict = {"$set": {"active": new_active}}
    if not new_active:
        update["$unset"] = {"active_token": ""}
    users_col.update_one({"_id": oid}, update)
    return {"success": True, "active": new_active}


@router.patch("/{user_id}")
def update_admin_user(user_id: str, body: UserUpdateIn, _admin: dict = Depends(require_super_admin)):
    """Edit an admin user's email, name, password, or role."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    user = users_col.find_one(tq({"_id": oid}))
    if not user:
        raise HTTPException(404, "User not found")
    updates: dict = {}
    if body.email is not None:
        clash = users_col.find_one(tq({"email": body.email, "_id": {"$ne": oid}}))
        if clash:
            raise HTTPException(409, "That email is already used by another user")
        updates["email"] = body.email.strip().lower()
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.role is not None:
        updates["role"] = body.role
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        updates["password_hash"] = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
        users_col.update_one({"_id": oid}, {"$unset": {"active_token": ""}})
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = user_email()
    users_col.update_one({"_id": oid}, {"$set": updates})
    return {"success": True}
