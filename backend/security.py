"""
security.py — Four-layer API security for Vedansh Medicare

Layer 1  Static API key      X-Api-Key header shared via _config.js
         Blocks clients that don't carry the key; stops casual scrapers.

Layer 2  Origin allowlist    Origin / Referer header check
         Rejects requests whose source domain isn't in ALLOWED_ORIGINS.
         Skipped when ALLOWED_ORIGINS is not set (safe default for local dev).

Layer 3  Short-lived page token   X-Page-Token header
         HMAC-SHA256 signed, expires in PAGE_TOKEN_TTL_MINUTES.
         Public website fetches one token at load time from /api/public-token
         and sends it on every subsequent API call — no login required.
         Admin dashboard requests are exempt if they carry a JWT bearer token.

Layer 4  Rate limiting        sliding-window counter per client IP (no extra deps)
         Applied as a decorator in main.py on write endpoints.
         /api/public-token itself is also rate-limited to prevent token farming.

Usage in main.py
----------------
    from security import apply_security, require_public_access, issue_page_token, rate_limit

    apply_security(app)          # call once after app = FastAPI(...)

    @app.get("/api/public-token")
    def get_page_token(request: Request, _: None = Depends(rate_limit(20, 60))):
        return issue_page_token()

    @app.get("/api/doctors")
    def list_doctors(..., _: None = Depends(require_public_access)):
        ...

    @app.post("/api/appointments", status_code=201)
    def create_appointment(request: Request, body: AppointmentIn,
                           _auth: None = Depends(require_public_access),
                           _rl:   None = Depends(rate_limit(10, 60))):
        ...
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
_raw_secret        = os.getenv("PAGE_TOKEN_SECRET",  "").strip()
PAGE_TOKEN_TTL     = int(os.getenv("PAGE_TOKEN_TTL_MINUTES", "60"))
_raw_origins       = os.getenv("ALLOWED_ORIGINS",    "").strip()
ALLOWED_ORIGINS    = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Generate an ephemeral secret if none is configured (tokens reset on restart).
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
# Simple sliding-window counter keyed by client IP.
# Works correctly for a single-process deployment (Render free tier, etc.).
# If you ever run multiple workers, swap _hits for a shared Redis store.

_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_hits: int, window_seconds: int) -> Callable:
    """
    FastAPI dependency factory — returns a dependency that enforces a
    sliding-window rate limit per client IP.

    Usage:
        @app.post("/api/appointments")
        def create_appointment(
            ...,
            _: None = Depends(rate_limit(10, 60)),
        ):
    """
    def _check(request: Request) -> None:
        ip  = request.client.host if request.client else "unknown"
        key = f"{ip}:{max_hits}:{window_seconds}"
        now = time.monotonic()
        window_start = now - window_seconds
        # Drop timestamps outside the current window.
        _hits[key] = [t for t in _hits[key] if t > window_start]
        if len(_hits[key]) >= max_hits:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )
        _hits[key].append(now)

    return _check


# ── Layer 1 + 2: Request middleware ──────────────────────────────────────────

# Paths that bypass both the API key and origin checks:
#  - /                    health-check
#  - /api/public-token    token issuer (would be circular if it required the key)
#  - /api/proxy/*         browser loads these as <img src> / <video src>;
#                         the browser cannot send custom headers for those requests
_OPEN_PATHS    = {"/", "/api/public-token"}
_OPEN_PREFIXES = ("/api/proxy/",)


def _is_open(path: str) -> bool:
    path = path.rstrip("/") or "/"
    return path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES)


def _cors_json(status: int, content: dict, request: Request) -> JSONResponse:
    """Return a JSONResponse with CORS headers so blocked responses reach the browser."""
    origin = request.headers.get("Origin", "*")
    return JSONResponse(
        status_code=status,
        content=content,
        headers={
            "Access-Control-Allow-Origin":  origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Api-Key, X-Page-Token",
            "Access-Control-Allow-Credentials": "true",
        },
    )


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Applies Layer 1 (API key) and Layer 2 (origin allowlist) to every request.

    Both layers are skipped for browser-direct requests (proxy endpoints) and
    for the token issuer endpoint. CORS preflight (OPTIONS) requests are also
    passed through so the browser CORS negotiation is not disrupted.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Pass CORS preflight requests through unconditionally.
        if request.method == "OPTIONS":
            return await call_next(request)

        if _is_open(request.url.path):
            return await call_next(request)

        # ── Layer 1: Static API key ───────────────────────────────────────
        if PUBLIC_API_KEY:
            incoming = request.headers.get("X-Api-Key", "")
            if not incoming or not hmac.compare_digest(
                incoming.encode(), PUBLIC_API_KEY.encode()
            ):
                return _cors_json(403, {"detail": "Forbidden"}, request)

        # ── Layer 2: Origin allowlist ─────────────────────────────────────
        if ALLOWED_ORIGINS:
            source = (
                request.headers.get("Origin")
                or request.headers.get("Referer")
                or ""
            )
            if not any(allowed in source for allowed in ALLOWED_ORIGINS):
                return _cors_json(403, {"detail": "Forbidden"}, request)

        return await call_next(request)


# ── Layer 3: Page token ───────────────────────────────────────────────────────

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64_decode(s: str) -> bytes:
    # Restore stripped padding before decoding.
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload_b64: str) -> str:
    return hmac.new(
        PAGE_TOKEN_SECRET.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()


def issue_page_token() -> dict:
    """
    Create and return a short-lived HMAC-signed page token.
    Called by the GET /api/public-token endpoint in main.py.
    """
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

    Accepts either:
      - A valid admin JWT bearer token (Authorization: Bearer <jwt>)
        so that the admin dashboard can call public GET endpoints without
        also needing a page token.
      - A valid page token (X-Page-Token: <token>)
        sent by the public website after fetching /api/public-token.

    Attach to a route with:  _: None = Depends(require_public_access)
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 15:
        # JWT present — main.py's _verify_token handles the real DB check.
        return
    _verify_page_token(request.headers.get("X-Page-Token", ""))


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def apply_security(app: FastAPI) -> None:
    """
    Register all security layers on the FastAPI app.
    Call once in main.py immediately after creating the app:

        apply_security(app)
    """
    app.add_middleware(SecurityMiddleware)
