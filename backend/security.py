"""
security.py — Multi-layer API security for Vedansh Medicare

Layer 1  API key validation (dual-mode)
         A) Site key: PUBLIC_API_KEY from .env, shared with _config.js.
            In PROD this key ONLY works when the request Origin matches
            ALLOWED_ORIGINS — copying it to Postman/curl won't work.
         B) External key: dynamic keys stored in MongoDB api_keys collection.
            SUPER_ADMIN creates these via POST /api/admin/api-keys.
            They bypass origin check but must be active and not expired.

Layer 2  Origin allowlist (PROD only)
         When APP_PROFILE=PROD, rejects requests whose Origin/Referer
         isn't in ALLOWED_ORIGINS. Skipped in DEV.

Layer 3  Short-lived page token   X-Page-Token header
         HMAC-SHA256 signed, expires in PAGE_TOKEN_TTL_MINUTES.
         Public website fetches one from /api/public-token at page load.
         Admin dashboard requests are exempt if they carry a Bearer token.

Layer 4  Rate limiting — sliding-window counter per client IP.

CORS     In PROD: only ALLOWED_ORIGINS.  In DEV: allow all ("*").
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets as _secrets
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# ── Environment config ────────────────────────────────────────────────────────

PUBLIC_API_KEY     = os.getenv("PUBLIC_API_KEY",     "").strip()
APP_PROFILE        = os.getenv("APP_PROFILE",        "DEV").strip().upper()
_raw_secret        = os.getenv("PAGE_TOKEN_SECRET",  "").strip()
PAGE_TOKEN_TTL     = int(os.getenv("PAGE_TOKEN_TTL_MINUTES", "60"))
_raw_origins       = os.getenv("ALLOWED_ORIGINS",    "").strip()
ALLOWED_ORIGINS    = [o.strip() for o in _raw_origins.split(",") if o.strip()]

IS_PROD = APP_PROFILE == "PROD"

if _raw_secret:
    PAGE_TOKEN_SECRET = _raw_secret
else:
    PAGE_TOKEN_SECRET = _secrets.token_urlsafe(32)
    print(
        "[SECURITY] PAGE_TOKEN_SECRET is not set in .env — "
        "using an ephemeral secret. Page tokens will expire on every restart. "
        "Set PAGE_TOKEN_SECRET to a stable random value in production."
    )


# ── Layer 4: In-process rate limiter ─────────────────────────────────────────

_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_hits: int, window_seconds: int) -> Callable:
    """FastAPI dependency factory — sliding-window rate limit per client IP."""
    def _check(request: Request) -> None:
        ip  = request.client.host if request.client else "unknown"
        key = f"{ip}:{max_hits}:{window_seconds}"
        now = time.monotonic()
        window_start = now - window_seconds
        _hits[key] = [t for t in _hits[key] if t > window_start]
        if len(_hits[key]) >= max_hits:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )
        _hits[key].append(now)
    return _check


# ── Open paths (bypass security) ────────────────────────────────────────────

_OPEN_API_PATHS    = {"/api/public-token"}
_OPEN_API_PREFIXES = ("/api/proxy/", "/api/file/")


def _is_open(path: str) -> bool:
    path = path.rstrip("/") or "/"
    if not path.startswith("/api"):
        return True
    return path in _OPEN_API_PATHS or any(path.startswith(p) for p in _OPEN_API_PREFIXES)


def _cors_json(status: int, content: dict, request: Request) -> JSONResponse:
    """Return a JSONResponse with CORS headers so blocked responses reach the browser."""
    origin = request.headers.get("Origin", "*")
    return JSONResponse(
        status_code=status,
        content=content,
        headers={
            "Access-Control-Allow-Origin":  origin if _origin_allowed(origin) else "",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Api-Key, X-Page-Token",
            "Access-Control-Allow-Credentials": "true",
        },
    )


# ── Origin validation ────────────────────────────────────────────────────────

def _origin_allowed(origin: str) -> bool:
    """Check if origin is in the allowed list. In DEV, all origins pass."""
    if not IS_PROD:
        return True
    if not ALLOWED_ORIGINS:
        return True  # No allowlist configured — allow all (misconfigured PROD)
    if not origin:
        return False
    return any(allowed in origin for allowed in ALLOWED_ORIGINS)


# ── API key validation (dual-mode) ──────────────────────────────────────────

def _validate_api_key(incoming_key: str, request: Request) -> bool:
    """
    Validate the X-Api-Key header against:
      A) Site key (PUBLIC_API_KEY) — requires matching origin in PROD
      B) External key from MongoDB — must be active and not expired
    Returns True if valid, False otherwise.
    """
    if not incoming_key:
        return False

    # A) Check against the site key
    if PUBLIC_API_KEY and hmac.compare_digest(incoming_key.encode(), PUBLIC_API_KEY.encode()):
        if IS_PROD:
            # Site key only works from whitelisted origins in PROD
            origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
            return _origin_allowed(origin)
        return True  # DEV — site key always valid

    # B) Check against dynamic API keys in MongoDB
    try:
        from database import api_keys_col
        now = datetime.now(timezone.utc)
        key_doc = api_keys_col.find_one({
            "key": incoming_key,
            "active": True,
        })
        if not key_doc:
            return False
        # Check expiry
        exp = key_doc.get("expires_at")
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                return False
        # Check IP restriction (if configured)
        allowed_ips = key_doc.get("allowed_ips") or []
        if allowed_ips:
            client_ip = request.client.host if request.client else ""
            if client_ip not in allowed_ips:
                return False
        # Update last_used timestamp
        api_keys_col.update_one(
            {"_id": key_doc["_id"]},
            {"$set": {"last_used_at": now, "last_used_ip": request.client.host if request.client else ""}},
        )
        return True
    except Exception:
        return False


# ── Layer 1 + 2: Security middleware ────────────────────────────────────────

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Applies API key validation and origin checks to every /api/ request.

    In PROD:
      - Site key (from _config.js) only works from ALLOWED_ORIGINS.
      - External DB keys work from any origin but must be active/unexpired.
      - Requests with no valid key are rejected.

    In DEV:
      - If PUBLIC_API_KEY is set, it's checked but origin is not enforced.
      - If PUBLIC_API_KEY is empty, all requests pass (no key required).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        if _is_open(request.url.path):
            return await call_next(request)

        # ── Layer 1: API key (site key or external DB key) ────────────
        incoming_key = request.headers.get("X-Api-Key", "")

        # If no site key is configured in env, skip key validation entirely
        if PUBLIC_API_KEY or IS_PROD:
            if not _validate_api_key(incoming_key, request):
                return _cors_json(403, {"detail": "Invalid or missing API key"}, request)

        # ── Layer 2: Origin check (PROD only, for non-DB-key requests) ──
        if IS_PROD and ALLOWED_ORIGINS:
            origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
            # External DB keys already passed validation above — they bypass origin.
            # But we still enforce origin for site-key requests.
            is_external_key = (
                incoming_key
                and PUBLIC_API_KEY
                and not hmac.compare_digest(incoming_key.encode(), PUBLIC_API_KEY.encode())
            )
            if not is_external_key and not _origin_allowed(origin):
                return _cors_json(403, {"detail": "Origin not allowed"}, request)

        return await call_next(request)


# ── Layer 3: Page token ───────────────────────────────────────────────────────

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload_b64: str) -> str:
    return hmac.new(
        PAGE_TOKEN_SECRET.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()


def issue_page_token() -> dict:
    """Create and return a short-lived HMAC-signed page token."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=PAGE_TOKEN_TTL)
    payload_b64 = _b64_encode(
        json.dumps({"type": "page", "exp": exp.timestamp()}, separators=(",", ":")).encode()
    )
    token = f"{payload_b64}.{_sign(payload_b64)}"
    return {"token": token, "expires_in": PAGE_TOKEN_TTL * 60}


def _verify_page_token(raw: str) -> None:
    """Raise HTTP 401 if the token is missing, tampered, or expired."""
    if not raw or "." not in raw:
        raise HTTPException(status_code=401, detail="Unauthorised")
    try:
        payload_b64, sig = raw.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload_b64), sig):
            raise HTTPException(status_code=401, detail="Unauthorised")
        payload = json.loads(_b64_decode(payload_b64))
        if payload.get("type") != "page":
            raise HTTPException(status_code=401, detail="Unauthorised")
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            raise HTTPException(status_code=401, detail="Session expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorised")


def require_public_access(request: Request) -> None:
    """
    FastAPI dependency for public endpoints.
    Accepts either a Bearer token (admin) or a page token (public website).
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 15:
        return
    _verify_page_token(request.headers.get("X-Page-Token", ""))


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def apply_security(app: FastAPI) -> None:
    """Register all security layers on the FastAPI app."""
    app.add_middleware(SecurityMiddleware)
    if IS_PROD:
        if ALLOWED_ORIGINS:
            print(f"[SECURITY] PROD mode — CORS restricted to: {', '.join(ALLOWED_ORIGINS)}")
        else:
            print("[SECURITY] WARNING: PROD mode but ALLOWED_ORIGINS is empty — all origins allowed!")
    else:
        print("[SECURITY] DEV mode — CORS allows all origins")
