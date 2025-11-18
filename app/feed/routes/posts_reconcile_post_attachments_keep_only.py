# app/feed/routes/posts_reconcile_post_attachments_keep_only.py
from __future__ import annotations
from typing import List
from datetime import datetime
from app.extensions import db
from app.feed.models import FeedAttachment
from app.feed.routes.util_has_col import _has_col

def _reconcile_post_attachments_keep_only(post, keep_ids: List[int]):
    """
    Keep only attachments whose IDs are in keep_ids. Remove others.
    If FeedAttachment has is_deleted: soft delete; otherwise hard delete.
    """
    if keep_ids is None:
        return
    keep_set = set(int(x) for x in keep_ids if x is not None)

    q = FeedAttachment.query.filter_by(post_id=getattr(post, "id", None))
    all_atts = q.all()
    for att in all_atts:
        aid = getattr(att, "id", None)
        if aid is None:
            continue
        if int(aid) in keep_set:
            continue
        # remove this attachment
        if _has_col(FeedAttachment, "is_deleted"):
            try:
                att.is_deleted = True
                if _has_col(FeedAttachment, "updated_at"):
                    att.updated_at = datetime.utcnow()
                db.session.add(att)
            except Exception:
                db.session.delete(att)
        else:
            db.session.delete(att)
