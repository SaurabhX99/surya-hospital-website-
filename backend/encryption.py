"""
encryption.py — AES-256-CBC payload encryption for API communication

When AES_ENCRYPTION_KEY is set (base64-encoded 32-byte key), this middleware:
  - Decrypts incoming JSON request bodies that contain {"_enc": "<base64>"}
  - Encrypts outgoing 2xx JSON response bodies into {"_enc": "<base64>"}

Format:  base64( IV[16 bytes] || AES-CBC-PKCS7(plaintext) )

The same key must be shared with the frontend via APP_CONFIG.AES_ENCRYPTION_KEY.
When the key is not set, the middleware is a transparent pass-through.

Env vars:
    AES_ENCRYPTION_KEY   Base64-encoded 32-byte (256-bit) key
                         Generate: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ── Config ───────────────────────────────────────────────────────────────────

_KEY_B64 = os.getenv("AES_ENCRYPTION_KEY", "").strip()
AES_KEY: bytes | None = base64.b64decode(_KEY_B64) if _KEY_B64 else None

if AES_KEY and len(AES_KEY) != 32:
    raise ValueError(
        f"AES_ENCRYPTION_KEY must decode to exactly 32 bytes (got {len(AES_KEY)}). "
        "Generate one with: python -c \"import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
    )


# ── Encrypt / Decrypt helpers ────────────────────────────────────────────────

def aes_encrypt(plaintext: bytes) -> str:
    """Encrypt *plaintext* with AES-256-CBC + PKCS7 padding.
    Returns base64(IV ‖ ciphertext)."""
    if not AES_KEY:
        raise RuntimeError("Encryption key not configured")
    iv = os.urandom(16)
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode()


def aes_decrypt(payload_b64: str) -> bytes:
    """Decrypt base64(IV ‖ ciphertext) back to plaintext bytes."""
    if not AES_KEY:
        raise RuntimeError("Encryption key not configured")
    raw = base64.b64decode(payload_b64)
    iv, ct = raw[:16], raw[16:]
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


# ── Middleware ───────────────────────────────────────────────────────────────

class _EncryptionMiddleware(BaseHTTPMiddleware):
    """Transparent AES encryption layer for all /api/ JSON traffic."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # ── Fast exit when encryption is disabled ────────────────────────
        if not AES_KEY:
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"

        # Only touch /api/ paths; skip CORS preflight
        if not path.startswith("/api") or request.method == "OPTIONS":
            return await call_next(request)

        # ── Decrypt incoming JSON body ───────────────────────────────────
        content_type = request.headers.get("content-type", "")
        if (
            request.method in ("POST", "PUT", "PATCH")
            and "application/json" in content_type
        ):
            body = await request.body()
            if body:
                try:
                    data = json.loads(body)
                    if isinstance(data, dict) and "_enc" in data:
                        decrypted = aes_decrypt(data["_enc"])
                        # Replace both the cached body AND the receive callable
                        # so downstream middleware / route handlers see decrypted data.
                        request._body = decrypted
                        async def _receive():
                            return {"type": "http.request", "body": decrypted}
                        request._receive = _receive
                except Exception:
                    pass  # Not encrypted or malformed — pass through as-is

        response = await call_next(request)

        # ── Encrypt outgoing JSON body (2xx only) ────────────────────────
        resp_ct = response.headers.get("content-type", "")
        if not (200 <= response.status_code < 300 and "application/json" in resp_ct):
            return response

        # Read the full response body from the iterator
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk.encode() if isinstance(chunk, str) else chunk

        encrypted = aes_encrypt(body_bytes)
        new_body = json.dumps({"_enc": encrypted}).encode()

        # Rebuild response preserving status + headers (update content-length)
        headers = {
            k: v for k, v in response.headers.items()
            if k.lower() != "content-length"
        }
        headers["content-length"] = str(len(new_body))

        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )


# ── Bootstrap ────────────────────────────────────────────────────────────────

def apply_encryption(app: FastAPI) -> None:
    """Register the encryption middleware on the app.
    Call BEFORE other middleware so it sits closest to the route handlers."""
    app.add_middleware(_EncryptionMiddleware)
    if AES_KEY:
        print("[ENCRYPTION] AES-256-CBC payload encryption is ACTIVE.")
    else:
        print("[ENCRYPTION] AES_ENCRYPTION_KEY not set — encryption disabled (pass-through).")
