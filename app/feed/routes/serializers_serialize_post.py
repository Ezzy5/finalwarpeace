# app/feed/routes/serializers_serialize_post.py
from __future__ import annotations
from typing import Dict
from datetime import timezone
from app.feed.models import FeedPost

def serialize_post(post: "FeedPost") -> Dict:
    """Return a FeedPost as a safe JSON-friendly dict with UTC timestamp."""
    created = getattr(post, "created_at", None)
    if created is not None:
        created_iso = created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        created_iso = None

    return {
        "id": getattr(post, "id", None),
        "title": getattr(post, "title", None),
        "html": getattr(post, "html", None),
        "author_id": getattr(post, "author_id", None),
        "audience_type": getattr(post, "audience_type", None),
        "audience_id": getattr(post, "audience_id", None),
        "created_at": created_iso,
        "is_deleted": bool(getattr(post, "is_deleted", False)),
    }
