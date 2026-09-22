"""
FAQ endpoints — CRUD for frequently asked questions.
"""
from __future__ import annotations

from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import faqs_col
from models import FaqIn, FaqUpdate
from security import require_public_access
from services.formatters import fmt_faq

router = APIRouter(prefix="/api/faqs", tags=["FAQs"])


@router.get("")
def list_faqs(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"active": True})
    if search:
        q["$or"] = [
            {"question": {"$regex": search, "$options": "i"}},
            {"answer": {"$regex": search, "$options": "i"}},
        ]
    return paginated(faqs_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_faq, page=page, limit=limit)


@router.post("", status_code=201)
def create_faq(body: FaqIn, _: None = Depends(require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["updated_by"]  = user_email()
    result = faqs_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{faq_id}")
def update_faq(faq_id: str, body: FaqUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(faq_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    patch["updated_by"] = user_email()
    result = faqs_col.update_one(tq({"_id": oid}), {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/{faq_id}")
def delete_faq(faq_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(faq_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = faqs_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
