"""
Hero stats endpoints — CRUD for homepage counter statistics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import hero_stats_col
from models import StatIn, StatUpdate
from security import require_public_access
from services.formatters import fmt_stat

router = APIRouter(prefix="/api/hero-stats", tags=["Hero Stats"])


@router.get("")
def list_hero_stats(
    show_all: bool = False,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"active": True})
    return paginated(hero_stats_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_stat, page=page, limit=limit)


@router.post("", status_code=201)
def create_hero_stat(body: StatIn, _: None = Depends(require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = user_email()
    result = hero_stats_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{stat_id}")
def update_hero_stat(stat_id: str, body: StatUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(stat_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update")
    updates["updated_by"] = user_email()
    hero_stats_col.update_one(tq({"_id": oid}), {"$set": updates})
    return {"success": True}


@router.delete("/{stat_id}")
def delete_hero_stat(stat_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(stat_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = hero_stats_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
