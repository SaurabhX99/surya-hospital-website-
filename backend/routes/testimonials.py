"""
Testimonial endpoints — CRUD with public submission and admin approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo import DESCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import testimonials_col
from models import TestimonialIn, TestimonialUpdate
from security import require_public_access, rate_limit
from services.formatters import fmt_testimonial

router = APIRouter(prefix="/api/testimonials", tags=["Testimonials"])


@router.get("")
def list_testimonials(
    show_all: bool = False,
    search: Optional[str] = None,
    approved: Optional[bool] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"approved": True})
    if approved is not None and show_all:
        q["approved"] = approved
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"text": {"$regex": search, "$options": "i"}},
        ]
    return paginated(testimonials_col, q, sort_field="created_at", sort_dir=DESCENDING,
                     fmt_fn=fmt_testimonial, page=page, limit=limit)


@router.post("", status_code=201)
def create_testimonial(request: Request, body: TestimonialIn,
                       _auth: None = Depends(require_public_access),
                       _rl:   None = Depends(rate_limit(5, 60))):
    doc = body.model_dump()
    doc["approved"]    = False
    doc["tenant_name"] = tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    result = testimonials_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{test_id}")
def update_testimonial(test_id: str, body: TestimonialUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(test_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = user_email()
    result = testimonials_col.update_one(tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/{test_id}")
def delete_testimonial(test_id: str):
    try:
        oid = ObjectId(test_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = testimonials_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
