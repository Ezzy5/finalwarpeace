# app/feed/routes/pins_user_pinned.py
from __future__ import annotations
from app.extensions import db
from app.feed.models import FeedPinnedPost

def _user_pinned(post_id: int, user_id: int) -> bool:
    try:
        return db.session.query(FeedPinnedPost).filter_by(
            post_id=post_id, user_id=user_id
        ).first() is not None
    except Exception:
        return False
