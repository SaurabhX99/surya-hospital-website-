"""
File upload & serve endpoints — GridFS-backed image/video storage.
"""
from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from auth import require_admin
from config import BASE_URL
from database import fs
from logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Uploads"])

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "image/avif", "image/bmp", "image/tiff",
    "video/mp4", "video/webm", "video/ogg",
}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB


@router.post("/api/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    _: None = Depends(require_admin),
):
    """Upload a file to GridFS. Returns the serve URL."""
    ct = file.content_type or "application/octet-stream"
    if ct not in ALLOWED_TYPES:
        raise HTTPException(400, f"File type '{ct}' not allowed. Accepted: images and videos.")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max {MAX_FILE_SIZE // (1024*1024)} MB.")

    try:
        file_id = fs.put(
            data,
            filename=file.filename or "upload",
            content_type=ct,
        )
    except Exception as e:
        logger.error("upload_file failed", extra={"error": str(e)})
        raise HTTPException(503, "Failed to store file")

    url = f"{BASE_URL}/api/file/{file_id}"
    return {"success": True, "file_id": str(file_id), "url": url}


@router.get("/api/file/{file_id}")
def serve_file(file_id: str):
    """Serve a file from GridFS by its ObjectId."""
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(400, "Invalid file ID")

    try:
        grid_out = fs.get(oid)
    except Exception:
        raise HTTPException(404, "File not found")

    ct = grid_out.content_type or "application/octet-stream"
    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Access-Control-Allow-Origin": "*",
    }
    return Response(content=grid_out.read(), media_type=ct, headers=headers)


@router.delete("/api/file/{file_id}")
def delete_file(file_id: str, _: None = Depends(require_admin)):
    """Delete a file from GridFS."""
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(400, "Invalid file ID")
    try:
        fs.delete(oid)
        return {"success": True}
    except Exception as e:
        logger.error("delete_file failed", extra={"error": str(e)})
        raise HTTPException(503, "Failed to delete file")
