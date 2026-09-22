"""
Facilities endpoints — CRUD for hospital facilities (ICU, OT, etc.).
"""
from __future__ import annotations

from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import facilities_col
from models import FacilityIn, FacilityUpdate
from security import require_public_access
from services.formatters import fmt_facility

router = APIRouter(prefix="/api/facilities", tags=["Facilities"])


@router.get("")
def list_facilities(
    show_all: bool = False,
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"active": True})
    if category:
        q["category"] = category
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"short_desc": {"$regex": search, "$options": "i"}},
        ]
    return paginated(facilities_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_facility, page=page, limit=limit)


@router.post("", status_code=201)
def create_facility(body: FacilityIn, _: None = Depends(require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["updated_by"]  = user_email()
    result = facilities_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{facility_id}")
def update_facility(facility_id: str, body: FacilityUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(facility_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    patch["updated_by"] = user_email()
    result = facilities_col.update_one(tq({"_id": oid}), {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/{facility_id}")
def delete_facility(facility_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(facility_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = facilities_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
