# app/feed/routes/comments_get_comment_flat.py
from __future__ import annotations
from app.extensions import db
from app.feed.models import FeedComment

def _get_comment_flat(comment_id: int) -> "FeedComment | None":
    return db.session.get(FeedComment, comment_id)
