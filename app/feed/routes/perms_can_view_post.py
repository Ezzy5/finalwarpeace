# app/feed/routes/perms_can_view_post.py
from __future__ import annotations
from typing import Any
from app.extensions import db
from app.models import User  # noqa: F401
from app.feed.models import FeedPost, FeedPostAllowedUser
from app.feed.routes.util_is_admin import _is_admin

def _can_view_post(u: "User", p: "FeedPost") -> bool:
    try:
        if _is_admin(u):
            return True
        at = (getattr(p, "audience_type", "all") or "all").strip()
        if at == "all":
            return True
        if at == "users":
            return db.session.query(FeedPostAllowedUser).filter_by(
                post_id=getattr(p, "id", None),
                user_id=getattr(u, "id", None)
            ).first() is not None
        if at == "sector":
            try:
                return (
                    getattr(u, "department_id", None) is not None
                    and int(getattr(u, "department_id")) == int(getattr(p, "audience_id", 0) or 0)
                )
            except Exception:
                return False
        return False
    except Exception:
        return False
