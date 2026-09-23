"""
Media & gallery endpoints — CRUD, gallery config, and Google Drive proxy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import media_col, gallery_cfg_col
from logging_config import get_logger
from models import MediaIn, MediaUpdate, GalleryConfigIn
from security import require_public_access
from services.formatters import fmt_media

logger = get_logger(__name__)
router = APIRouter(tags=["Media & Gallery"])


# ── Media CRUD ───────────────────────────────────────────────────────

@router.get("/api/media")
def list_media(
    gallery: bool = False,
    search: Optional[str] = None,
    type: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq({"show_in_gallery": True}) if gallery else tq()
    if type:
        q["type"] = type
    if search:
        q["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"alt": {"$regex": search, "$options": "i"}},
        ]
    return paginated(media_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_media, page=page, limit=limit)


@router.post("/api/media", status_code=201)
def create_media(body: MediaIn, _: None = Depends(require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = user_email()
    result = media_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/api/media/{media_id}")
def update_media(media_id: str, body: MediaUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = user_email()
    result = media_col.update_one(tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/api/media/{media_id}")
def delete_media(media_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = media_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Gallery Config ───────────────────────────────────────────────────

@router.get("/api/gallery-config")
def get_gallery_config(_: None = Depends(require_public_access)):
    doc = gallery_cfg_col.find_one(tq())
    if not doc:
        return {"autoplay": True, "interval": 5000, "transition": "fade", "show_captions": True}
    doc.pop("_id", None)
    doc.pop("tenant_name", None)
    return doc


@router.patch("/api/gallery-config")
def update_gallery_config(body: GalleryConfigIn, _: None = Depends(require_admin)):
    data = body.model_dump(exclude_unset=True)
    data["updated_by"] = user_email()
    gallery_cfg_col.update_one(tq(), {"$set": data}, upsert=True)
    return {"success": True}


# ── Google Drive Proxy ───────────────────────────────────────────────

@router.get("/api/proxy/image")
async def proxy_drive_image(id: str):
    """Proxy a Google Drive image by file ID to avoid CORS / auth walls."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://drive.google.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    candidates = [
        f"https://lh3.googleusercontent.com/d/{id}=s1200",
        f"https://drive.google.com/thumbnail?id={id}&sz=w1200",
        f"https://drive.google.com/uc?export=download&id={id}&confirm=t",
    ]
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=headers) as client:
            for url in candidates:
                r = await client.get(url)
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and "image" in ct:
                    resp_headers = {
                        "Cache-Control": "public, max-age=86400",
                        "Access-Control-Allow-Origin": "*",
                    }
                    return Response(content=r.content, media_type=ct.split(";")[0], headers=resp_headers)
                logger.debug("Proxy attempt failed", extra={"url": url, "status_code": r.status_code, "content_type": ct})
        raise HTTPException(502, "Could not fetch image from Drive — ensure the file is shared publicly")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("proxy_drive_image failed", extra={"error": str(e)})
        raise HTTPException(502, "Could not fetch image from Drive")


@router.get("/api/proxy/video")
async def proxy_drive_video(id: str, request: Request):
    """Stream a Google Drive video by file ID so <video> autoplay works."""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }
    if "range" in request.headers:
        req_headers["Range"] = request.headers["range"]

    candidates = [
        f"https://drive.google.com/uc?export=download&id={id}&confirm=t",
        f"https://drive.google.com/uc?export=view&id={id}",
    ]
    try:
        for url in candidates:
            client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(15, read=None))
            r = await client.get(url, headers=req_headers)
            ct = r.headers.get("content-type", "")
            if r.status_code in (200, 206) and "video" in ct:
                resp_headers = {
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "max-age=3600",
                    "Access-Control-Allow-Origin": "*",
                }
                for h in ("content-length", "content-range", "last-modified"):
                    if h in r.headers:
                        resp_headers[h] = r.headers[h]

                async def _stream(r=r, client=client):
                    try:
                        async for chunk in r.aiter_bytes(65536):
                            yield chunk
                    finally:
                        await client.aclose()

                return StreamingResponse(
                    _stream(),
                    status_code=r.status_code,
                    headers=resp_headers,
                    media_type=ct.split(";")[0],
                )
            await client.aclose()
            logger.debug("Video proxy attempt failed", extra={"url": url, "status_code": r.status_code})
        raise HTTPException(502, "Could not stream video from Drive — ensure the file is shared publicly")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("proxy_drive_video failed", extra={"error": str(e)})
        raise HTTPException(502, "Could not stream video from Drive")
