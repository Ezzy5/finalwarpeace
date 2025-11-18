# app/feed/routes/comments_get_comment_nested.py
from __future__ import annotations
from app.feed.models import FeedComment

def _get_comment_nested(post_id: int, comment_id: int) -> "FeedComment | None":
    return FeedComment.query.filter_by(id=comment_id, post_id=post_id).first()
