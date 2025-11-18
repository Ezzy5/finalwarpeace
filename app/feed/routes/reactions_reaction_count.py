# app/feed/routes/reactions_reaction_count.py
from __future__ import annotations
from app.extensions import db
from app.feed.models import FeedReaction

def _reaction_count(post_id: int) -> int:
    try:
        return int(db.session.query(FeedReaction).filter_by(post_id=post_id, emoji="👍").count())
    except Exception:
        return 0
