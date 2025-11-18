# app/feed/routes/drive_ensure_drive_dir.py
from __future__ import annotations
import os
from app.feed.routes.util_static_root import _static_root

# Local constant so this module is self-contained
DRIVE_FS_SUBDIR = os.path.join("uploads", "drive")

def _ensure_drive_dir() -> str:
    """
    Ensure static/uploads/drive exists and return its absolute path.
    Replace this with your real Drive storage root if needed.
    """
    path = os.path.join(_static_root(), DRIVE_FS_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path
