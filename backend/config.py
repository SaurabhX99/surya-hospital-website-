"""
Application configuration — environment variables, constants, and per-request context.

All settings are loaded once at import time from the process environment
(populated by .env via python-dotenv in main.py).
"""
from __future__ import annotations

import contextvars
import os

from pymongo import ASCENDING, DESCENDING

# ── Tenant & base URL ────────────────────────────────────────────────
TENANT_NAME = os.getenv("TENANT_NAME", "vedansh_medicare").strip()
BASE_URL    = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

# ── Per-request context variables ────────────────────────────────────
# Set by tenant middleware on every request; used by route handlers.
_request_tenant: contextvars.ContextVar[str] = contextvars.ContextVar("_request_tenant")
_request_user_email: contextvars.ContextVar[str] = contextvars.ContextVar("_request_user_email", default="")


def tenant() -> str:
    """Return the tenant name for the current request."""
    return _request_tenant.get(TENANT_NAME)


def user_email() -> str:
    """Return the email of the currently authenticated admin, or empty string."""
    return _request_user_email.get("")


def tq(extra: dict | None = None) -> dict:
    """Return a base MongoDB query scoped to the current request's tenant."""
    return {"tenant_name": tenant(), **(extra or {})}


# ── Pagination helper ────────────────────────────────────────────────
def paginated(collection, query: dict, *, sort_field: str = "created_at",
              sort_dir: int = DESCENDING, fmt_fn, page: int | None = None,
              limit: int = 20):
    """
    Return items from *collection* matching *query*.

    If *page* is provided (>=1), return a paginated envelope:
        {"total": N, "page": P, "limit": L, "items": [...]}
    Otherwise return a flat list for backward compatibility.
    """
    cursor = collection.find(query).sort(sort_field, sort_dir)
    if page is not None:
        page = max(1, page)
        total = collection.count_documents(query)
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        items = [fmt_fn(d) for d in cursor]
        return {"total": total, "page": page, "limit": limit, "items": items}
    return [fmt_fn(d) for d in cursor]


# ── Appointment status normalisation map ─────────────────────────────
STATUS_MAP = {
    "BOOKED": "confirmed", "PENDING": "pending",
    "CANCELLED": "cancelled", "COMPLETED": "completed",
}

# ── Legacy Twilio env vars (kept for backward-compatible notifications) ──
TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID",  "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN",    "")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER",   "")
TWILIO_WA    = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# ── Startup admin credentials ────────────────────────────────────────
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

# ── Docs toggle ──────────────────────────────────────────────────────
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"
