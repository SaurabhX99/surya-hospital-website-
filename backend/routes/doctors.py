"""
Doctor endpoints — CRUD operations for the doctors collection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import DESCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import doctors_col
from logging_config import get_logger
from models import DoctorIn, DoctorUpdate
from security import require_public_access
from services.formatters import fmt_doctor

logger = get_logger(__name__)
router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.get("")
def list_doctors(
    featured: Optional[bool] = None,
    show_all: bool = False,
    search: Optional[str] = None,
    department: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    try:
        query = tq() if show_all else tq({"active": True})
        if featured is not None:
            query["featured"] = featured
        if department:
            query["department"] = {"$regex": department, "$options": "i"}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"specialty": {"$regex": search, "$options": "i"}},
                {"qualification": {"$regex": search, "$options": "i"}},
            ]
        return paginated(doctors_col, query, sort_field="created_at", sort_dir=DESCENDING,
                         fmt_fn=fmt_doctor, page=page, limit=limit)
    except Exception as e:
        logger.error("list_doctors failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.post("", status_code=201)
def create_doctor(body: DoctorIn, _: None = Depends(require_admin)):
    try:
        doc = body.model_dump()
        doc["tenant_name"] = tenant()
        doc["created_at"]  = datetime.now(timezone.utc)
        doc["updated_by"]  = user_email()
        result = doctors_col.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        logger.error("create_doctor failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.patch("/{doctor_id}")
def update_doctor(doctor_id: str, body: DoctorUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(doctor_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_by"] = user_email()
        result = doctors_col.update_one(tq({"_id": oid}), {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_doctor failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.delete("/{doctor_id}")
def delete_doctor(doctor_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(doctor_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        result = doctors_col.delete_one(tq({"_id": oid}))
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_doctor failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")
