"""
Audit log endpoint — paginated purge/deletion audit trail for SUPER_ADMIN.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pymongo import DESCENDING

from auth import require_super_admin
from config import tq
from database import audit_logs_col

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@router.get("")
def list_audit_logs(
    page: int = 1,
    limit: int = 50,
    _admin: dict = Depends(require_super_admin),
):
    """Return paginated audit log entries for this tenant, newest first."""
    q = tq()
    skip = (page - 1) * limit
    total = audit_logs_col.count_documents(q)
    docs = list(
        audit_logs_col.find(q)
        .sort("timestamp", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d.pop("tenant_name", None)
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            d["timestamp"] = ts.isoformat()
    return {"total": total, "page": page, "limit": limit, "logs": docs}
