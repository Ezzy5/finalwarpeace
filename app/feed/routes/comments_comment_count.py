# app/feed/routes/comments_comment_count.py
from __future__ import annotations
from app.feed.models import FeedComment
from app.feed.routes.util_has_col import _has_col

def _comment_count(post_id: int) -> int:
    try:
        q = FeedComment.query.filter_by(post_id=post_id)
        if _has_col(FeedComment, "is_deleted"):
            q = q.filter_by(is_deleted=False)
        return int(q.count())
    except Exception:
        return 0
