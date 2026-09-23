"""
Awards & Recognition endpoints — CRUD for hospital awards.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import awards_col
from models import AwardIn, AwardUpdate
from security import require_public_access
from services.formatters import fmt_award

router = APIRouter(prefix="/api/awards", tags=["Awards"])


@router.get("")
def list_awards(
    show_all: bool = False,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"active": True})
    return paginated(awards_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_award, page=page, limit=limit)


@router.post("", status_code=201)
def create_award(body: AwardIn, _: None = Depends(require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = user_email()
    result = awards_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{award_id}")
def update_award(award_id: str, body: AwardUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(award_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(400, "Nothing to update")
    patch["updated_by"] = user_email()
    result = awards_col.update_one(tq({"_id": oid}), {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/{award_id}")
def delete_award(award_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(award_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = awards_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
