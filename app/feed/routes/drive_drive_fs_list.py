# app/feed/routes/drive_drive_fs_list.py
from __future__ import annotations
import os
import mimetypes
from typing import Dict, Any
from app.feed.routes.drive_ensure_drive_dir import _ensure_drive_dir, DRIVE_FS_SUBDIR
from app.feed.routes.util_static_url import _static_url

def _drive_fs_list(q: str, limit: int, cursor: str | None) -> Dict[str, Any]:
    """
    Default picker data source: list files from static/uploads/drive.
    Cursor is a numeric offset encoded as string. Returns items + next_cursor.
    Replace this with a DB query if your Drive is in SQL.
    """
    root = _ensure_drive_dir()
    # gather regular files
    entries = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isfile(full):
            continue
        if q and q.lower() not in name.lower():
            continue
        size = None
        try:
            size = os.path.getsize(full)
        except OSError:
            pass
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        rel = f"{DRIVE_FS_SUBDIR}/{name}".replace("\\", "/")
        item = {
            "file_url": _static_url(rel),
            "file_name": name,
            "file_type": mime,
            "file_size": size,
            "preview_url": _static_url(rel) if mime.startswith("image/") else None,
        }
        entries.append(item)

    # paginate
    try:
        off = int(cursor or "0")
    except Exception:
        off = 0
    off = max(0, off)
    slice_ = entries[off: off + limit]
    next_cur = None
    if off + limit < len(entries):
        next_cur = str(off + limit)
    return {"items": slice_, "next_cursor": next_cur}
