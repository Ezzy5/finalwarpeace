# app/feed/routes/util_cursor_encode.py
from __future__ import annotations
from datetime import datetime
from app.feed.models import FeedPost  # adjust if your model path differs

def _cursor_encode(post: FeedPost | None) -> str | None:
    if not post:
        return None
    dt = getattr(post, "created_at", None) or datetime.utcnow()
    ms = int(dt.timestamp() * 1000)
    return f"{ms}.{post.id}"
