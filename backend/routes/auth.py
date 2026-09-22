"""
Authentication routes — login, MFA, logout, verify, refresh (with token rotation).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
import pyotp
from fastapi import APIRouter, HTTPException, Request

from auth.dependencies import get_bearer, verify_token
from config import TENANT_NAME
from database import users_col
from logging_config import get_logger
from models import LoginIn, MFAVerifyIn

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _complete_mfa_login(user: dict) -> dict:
    """Issue a full session token, enforcing single active session."""
    token      = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    users_col.update_one(
        {"_id": user["_id"]},
        {
            "$set":   {"active_token": token, "token_expires_at": expires_at,
                       "last_login": datetime.now(timezone.utc)},
            "$unset": {"pre_auth_token": "", "pre_auth_expires_at": ""},
        },
    )
    return {
        "token":         token,
        "name":          user.get("name", "Admin"),
        "role":          user.get("role", "Admin"),
        "email":         user["email"],
        "expires_at":    expires_at.isoformat(),
        "tenant_name":   user.get("tenant_name", TENANT_NAME),
        "hospital_name": user.get("hospital_name", "Hospital Admin"),
    }


def _resolve_pre_token(pre_token: str) -> dict:
    """Look up and validate a pre-auth token; raises 401 on failure."""
    user = users_col.find_one({"pre_auth_token": pre_token})
    if not user:
        raise HTTPException(401, "Invalid or expired session. Please login again.")
    exp = user.get("pre_auth_expires_at")
    if not exp:
        raise HTTPException(401, "Session expired. Please login again.")
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise HTTPException(401, "Session expired. Please login again.")
    return user


@router.post("/login")
def auth_login(body: LoginIn):
    email = body.email.strip().lower()
    user  = users_col.find_one({"email": email})
    if not user:
        raise HTTPException(401, "Invalid email or password")
    pw_hash = user.get("password_hash")
    if isinstance(pw_hash, str):
        pw_hash = pw_hash.encode()
    if not pw_hash or not bcrypt.checkpw(body.password.encode(), pw_hash):
        raise HTTPException(401, "Invalid email or password")
    logger.info("Admin login", extra={"user_email": email})
    return _complete_mfa_login(user)


@router.post("/mfa/verify")
def mfa_verify(body: MFAVerifyIn):
    """Step 2 for users who already have TOTP set up."""
    user = _resolve_pre_token(body.pre_token)
    totp_secret = user.get("totp_secret")
    if not totp_secret:
        raise HTTPException(400, "MFA not configured for this account.")
    if not pyotp.TOTP(totp_secret).verify(body.code.strip(), valid_window=1):
        raise HTTPException(401, "Invalid verification code. Please try again.")
    return _complete_mfa_login(user)


@router.post("/mfa/setup")
def mfa_setup_confirm(body: MFAVerifyIn):
    """Step 2 for first-time setup: confirm TOTP code and activate MFA."""
    user = _resolve_pre_token(body.pre_token)
    totp_secret = user.get("totp_secret_pending")
    if not totp_secret:
        raise HTTPException(400, "No pending MFA setup found.")
    if not pyotp.TOTP(totp_secret).verify(body.code.strip(), valid_window=1):
        raise HTTPException(401, "Invalid verification code. Please try again.")
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"totp_secret": totp_secret}, "$unset": {"totp_secret_pending": ""}},
    )
    return _complete_mfa_login(user)


@router.post("/logout")
def auth_logout(request: Request):
    token = get_bearer(request)
    if token:
        users_col.update_one(
            {"active_token": token},
            {"$unset": {"active_token": "", "token_expires_at": ""}}
        )
    return {"success": True}


@router.get("/verify")
def auth_verify(request: Request):
    token = get_bearer(request)
    user  = verify_token(token)
    if not user:
        raise HTTPException(401, "Token invalid or expired")
    exp = user["token_expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return {
        "name":          user.get("name", "Admin"),
        "role":          user.get("role", "Admin"),
        "email":         user["email"],
        "expires_at":    exp.isoformat(),
        "tenant_name":   user.get("tenant_name", TENANT_NAME),
        "hospital_name": user.get("hospital_name", "Hospital Admin"),
    }


@router.post("/refresh")
def auth_refresh(request: Request):
    token = get_bearer(request)
    user  = verify_token(token)
    if not user:
        raise HTTPException(401, "Token invalid or expired")
    # Rotate: issue a completely new token (invalidates the old one)
    new_token = secrets.token_urlsafe(32)
    new_exp   = datetime.now(timezone.utc) + timedelta(minutes=30)
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"active_token": new_token, "token_expires_at": new_exp}},
    )
    return {"token": new_token, "expires_at": new_exp.isoformat()}
