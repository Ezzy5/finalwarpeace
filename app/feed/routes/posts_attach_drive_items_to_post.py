# app/feed/routes/posts_attach_drive_items_to_post.py
from __future__ import annotations
import os
import mimetypes
from datetime import datetime
from typing import Dict, Any, List
from app.extensions import db
from app.feed.models import FeedPost, FeedAttachment
from app.feed.routes.util_has_col import _has_col

def _attach_drive_items_to_post(post: "FeedPost", drive_items: List[Dict[str, Any]], author_id: int):
    for it in (drive_items or []):
        file_url = (it.get("file_url") or "").strip()
        if not file_url:
            continue
        name = (it.get("file_name") or os.path.basename(file_url) or "file").strip()
        mime = (it.get("file_type") or mimetypes.guess_type(name)[0] or "application/octet-stream").strip()
        size = it.get("file_size")
        try:
            size = int(size) if size is not None else None
        except Exception:
            size = None
        preview = it.get("preview_url") if str(mime).startswith("image/") else it.get("preview_url")

        att_fields = dict(
            post_id=post.id,
            file_name=name,
            file_type=mime,
            file_size=size,
            file_url=file_url,
            preview_url=preview,
            uploaded_at=datetime.utcnow(),
        )
        if _has_col(FeedAttachment, "author_id"):
            att_fields["author_id"] = author_id

        db.session.add(FeedAttachment(**att_fields))
