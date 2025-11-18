# app/feed/routes/serializers_comment_to_dict.py
from __future__ import annotations
from app.feed.models import FeedComment

def _comment_to_dict(c: FeedComment, with_rel: bool = False, u=None) -> dict:
    """Convert a FeedComment SQLAlchemy model to a clean dict for JSON."""
    if not c:
        return {}

    d = {
        "id": c.id,
        "post_id": c.post_id,
        "html": getattr(c, "html", ""),
        "created_at": getattr(c, "created_at", None).isoformat() if getattr(c, "created_at", None) else None,
    }

    if with_rel:
        author = getattr(c, "author", None)
        d["author"] = {
            "id": getattr(author, "id", None),
            "full_name": getattr(author, "full_name", "Корисник"),
            "avatar_url": getattr(author, "avatar_url", "/static/img/avatar-placeholder.png"),
        }

    # Optional: if you store replies or attachments in comments
    if hasattr(c, "attachments"):
        d["attachments"] = [a.to_dict() for a in getattr(c, "attachments", [])]
    else:
        d["attachments"] = []

    return d
