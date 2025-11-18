# app/feed/routes/comments_serialize_comment.py
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any
from app.feed.models import FeedComment
from app.feed.routes.serializers_safe_author_dict import _safe_author_dict

def _serialize_comment(c: "FeedComment") -> Dict[str, Any]:
    return {
        "id": getattr(c, "id", None),
        "post_id": getattr(c, "post_id", None),
        "html": getattr(c, "html", "") or "",
        "created_at": (getattr(c, "created_at", None) or datetime.utcnow()).isoformat(),
        "updated_at": (getattr(c, "updated_at", None) or getattr(c, "created_at", None) or datetime.utcnow()).isoformat(),
        "author": _safe_author_dict(getattr(c, "author", None)),
    }
