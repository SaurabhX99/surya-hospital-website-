"""
Department endpoints — CRUD operations for hospital departments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import departments_col
from logging_config import get_logger
from models import DepartmentIn, DepartmentUpdate
from security import require_public_access
from services.formatters import fmt_department

logger = get_logger(__name__)
router = APIRouter(prefix="/api/departments", tags=["Departments"])


@router.get("")
def list_departments(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    try:
        query = tq() if show_all else tq({"active": True})
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"head_doctor": {"$regex": search, "$options": "i"}},
            ]
        return paginated(departments_col, query, sort_field="order", sort_dir=ASCENDING,
                         fmt_fn=fmt_department, page=page, limit=limit)
    except Exception as e:
        logger.error("list_departments failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.post("", status_code=201)
def create_department(body: DepartmentIn, _: None = Depends(require_admin)):
    try:
        doc = body.model_dump()
        doc["tenant_name"] = tenant()
        doc["created_at"]  = datetime.now(timezone.utc)
        doc["updated_by"]  = user_email()
        result = departments_col.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        logger.error("create_department failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.patch("/{dept_id}")
def update_department(dept_id: str, body: DepartmentUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_by"] = user_email()
        result = departments_col.update_one(tq({"_id": oid}), {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_department failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.delete("/{dept_id}")
def delete_department(dept_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        result = departments_col.delete_one(tq({"_id": oid}))
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_department failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")
