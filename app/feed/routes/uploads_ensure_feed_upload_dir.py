# app/feed/routes/uploads_ensure_feed_upload_dir.py
from __future__ import annotations
import os
from app.feed.routes.util_static_root import _static_root

def _ensure_feed_upload_dir() -> str:
    """Ensure static/uploads/feed exists and return its absolute path."""
    path = os.path.join(_static_root(), "uploads", "feed")
    os.makedirs(path, exist_ok=True)
    return path
