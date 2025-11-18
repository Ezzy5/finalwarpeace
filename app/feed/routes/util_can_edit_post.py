# app/feed/routes/util_can_edit_post.py
from __future__ import annotations
from app.models import User  # noqa: F401
from app.feed.models import FeedPost

def _can_edit_post(u: "User", p: "FeedPost") -> bool:
    try:
        return bool(getattr(u, "is_admin", False) or getattr(u, "is_superuser", False)) \
            or int(getattr(p, "author_id", 0)) == int(getattr(u, "id", -1))
    except Exception:
        return False
