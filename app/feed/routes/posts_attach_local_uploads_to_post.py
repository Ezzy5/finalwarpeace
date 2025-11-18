# app/feed/routes/posts_attach_local_uploads_to_post.py
from __future__ import annotations
import os
import mimetypes
from datetime import datetime
from typing import List
from app.extensions import db
from app.feed.models import FeedPost, FeedAttachment
from app.feed.routes.util_static_root import _static_root
from app.feed.routes.util_static_url import _static_url
from app.feed.routes.util_has_col import _has_col

def _attach_local_uploads_to_post(post: "FeedPost", rel_paths: List[str], author_id: int):
    for rel_path in (rel_paths or []):
        if not rel_path:
            continue
        rel_norm = rel_path.lstrip("/").replace("\\", "/")
        abs_path = os.path.join(_static_root(), rel_norm)
        file_name = os.path.basename(rel_norm)

        size = None
        try:
            size = os.path.getsize(abs_path)
        except OSError:
            pass

        mime = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        is_img = str(mime).startswith("image/")

        att_fields = dict(
            post_id=post.id,
            file_name=file_name,
            file_type=mime,
            file_size=size,
            file_url=_static_url(rel_norm),
            preview_url=_static_url(rel_norm) if is_img else None,
            uploaded_at=datetime.utcnow(),
        )
        if _has_col(FeedAttachment, "author_id"):
            att_fields["author_id"] = author_id

        db.session.add(FeedAttachment(**att_fields))
