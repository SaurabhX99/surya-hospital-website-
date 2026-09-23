"""
Blog endpoints — CRUD and Google Drive content proxy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pymongo import DESCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import blogs_col
from logging_config import get_logger
from models import BlogIn, BlogUpdate
from security import require_public_access
from services.formatters import fmt_blog, drive_content_url

logger = get_logger(__name__)
router = APIRouter(prefix="/api/blogs", tags=["Blogs"])


@router.get("")
def list_blogs(
    show_all: bool = False,
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    try:
        query = tq() if show_all else tq({"published": True})
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"author": {"$regex": search, "$options": "i"}},
                {"tags": {"$regex": search, "$options": "i"}},
            ]
        return paginated(blogs_col, query, sort_field="created_at", sort_dir=DESCENDING,
                         fmt_fn=fmt_blog, page=page, limit=limit)
    except Exception as e:
        logger.error("list_blogs failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.get("/{blog_id}")
def get_blog(blog_id: str, _: None = Depends(require_public_access)):
    try:
        doc = blogs_col.find_one(tq({"_id": ObjectId(blog_id)}))
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return fmt_blog(doc)


@router.post("", status_code=201)
def create_blog(body: BlogIn, _: None = Depends(require_admin)):
    doc = {
        "tenant_name": tenant(),
        "title":       body.title,
        "author":      body.author,
        "category":    body.category,
        "drive_link":  body.drive_link,
        "excerpt":     body.excerpt,
        "thumbnail":   body.thumbnail,
        "tags":        body.tags,
        "published":   body.published,
        "created_at":  datetime.now(timezone.utc),
        "updated_by":  user_email(),
    }
    try:
        result = blogs_col.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        logger.error("create_blog failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.patch("/{blog_id}")
def update_blog(blog_id: str, body: BlogUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_by"] = user_email()
        result = blogs_col.update_one(tq({"_id": oid}), {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_blog failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.delete("/{blog_id}")
def delete_blog(blog_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        result = blogs_col.delete_one(tq({"_id": oid}))
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_blog failed", extra={"error": str(e)})
        raise HTTPException(503, "Database temporarily unavailable")


@router.get("/{blog_id}/content")
async def get_blog_content(blog_id: str, _: None = Depends(require_public_access)):
    """Proxy the blog article content from Google Drive."""
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = blogs_col.find_one(tq({"_id": oid}), {"drive_link": 1})
    if not doc or not doc.get("drive_link"):
        raise HTTPException(404, "No content available for this blog post")
    content_url = drive_content_url(doc["drive_link"])
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            r = await client.get(content_url)
        if r.status_code != 200:
            raise HTTPException(502, "Could not fetch content from Drive")
        media_type = r.headers.get("content-type", "text/html").split(";")[0]
        return Response(content=r.content, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_blog_content failed", extra={"error": str(e)})
        raise HTTPException(502, "Could not fetch content from Drive")
