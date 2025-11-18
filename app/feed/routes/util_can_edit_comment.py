# app/feed/routes/util_can_edit_comment.py
from __future__ import annotations
from app.models import User  # noqa: F401
from app.feed.models import FeedComment

def _can_edit_comment(u: "User", c: "FeedComment") -> bool:
    try:
        return bool(getattr(u, "is_admin", False) or getattr(u, "is_superuser", False)) \
            or int(getattr(c, "author_id", 0)) == int(getattr(u, "id", -1))
    except Exception:
        return False
