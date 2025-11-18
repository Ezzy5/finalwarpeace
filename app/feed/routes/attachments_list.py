# app/feed/routes/attachments_list.py
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime
from app.feed.models import FeedPost

def _attachments_list(p: "FeedPost") -> List[Dict[str, Any]]:
    try:
        atts = getattr(p, "attachments", []) or []
        out: List[Dict[str, Any]] = []
        for att in atts:
            file_url = getattr(att, "file_url", None)
            ftype = getattr(att, "file_type", None) or ""
            is_image = str(ftype).startswith("image/")
            out.append({
                "id": getattr(att, "id", None),
                "file_name": getattr(att, "file_name", None),
                "file_type": ftype,
                "file_size": getattr(att, "file_size", None),
                "file_url": file_url,
                "preview_url": getattr(att, "preview_url", None) if is_image else getattr(att, "preview_url", None),
                "uploaded_at": (getattr(att, "uploaded_at", None) or datetime.utcnow()).isoformat(),
            })
        return out
    except Exception:
        return []
