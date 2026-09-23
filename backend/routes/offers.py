"""
Offers endpoints — CRUD for promotional offers/banners.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import offers_col
from models import OfferIn, OfferUpdate
from security import require_public_access
from services.formatters import fmt_offer

router = APIRouter(prefix="/api/offers", tags=["Offers"])


@router.get("")
def list_offers(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"active": True})
    if search:
        q["text"] = {"$regex": search, "$options": "i"}
    return paginated(offers_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_offer, page=page, limit=limit)


@router.post("", status_code=201)
def create_offer(body: OfferIn, _: None = Depends(require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = user_email()
    result = offers_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{offer_id}")
def update_offer(offer_id: str, body: OfferUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(offer_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = user_email()
    result = offers_col.update_one(tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/{offer_id}")
def delete_offer(offer_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(offer_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = offers_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
