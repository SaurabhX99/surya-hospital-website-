"""
MongoDB connection and collection references.

All collection handles are module-level singletons created at import time.
Route modules import the specific collections they need:

    from database import appointments_col, doctors_col
"""
from __future__ import annotations

import os

from pymongo import MongoClient

# ── Connection ───────────────────────────────────────────────────────
client = MongoClient(
    os.getenv("MONGO_URI", ""),
    tls=True,
    tlsAllowInvalidCertificates=True,
)
db = client[os.getenv("DATABASE_NAME", "").strip()]

# ── Collections ──────────────────────────────────────────────────────
appointments_col  = db["appointments"]
doctors_col       = db["doctors"]
departments_col   = db["departments"]
blogs_col         = db["blogs"]
media_col         = db["media"]
gallery_cfg_col   = db["gallery_config"]
testimonials_col  = db["testimonials"]
users_col         = db["admin_users"]
offers_col        = db["offers"]
insurance_col     = db["insurance_providers"]
partners_col      = db["partners"]
hero_stats_col    = db["hero_stats"]
sms_config_col    = db["sms_config"]
site_config_col   = db["site_config"]
sms_logs_col      = db["sms_logs"]
facilities_col    = db["facilities"]
faqs_col          = db["faqs"]
audit_logs_col    = db["audit_logs"]
api_keys_col      = db["api_keys"]          # dynamic API keys for external callers
