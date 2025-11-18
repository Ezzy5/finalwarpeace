# app/feed/routes/reactions_user_reacted.py
from __future__ import annotations
from app.extensions import db
from app.feed.models import FeedReaction

def _user_reacted(post_id: int, user_id: int) -> bool:
    try:
        return db.session.query(FeedReaction).filter_by(
            post_id=post_id, user_id=user_id, emoji="👍"
        ).first() is not None
    except Exception:
        return False
