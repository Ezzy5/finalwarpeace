# app/feed/routes/route_create_post.py
from __future__ import annotations

from typing import Any, Dict, List

from flask import request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost, FeedPostAllowedUser
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.serializers_post_to_dict import _post_to_dict
from app.feed.routes.posts_attach_local_uploads_to_post import (
    _attach_local_uploads_to_post,
)
from app.feed.routes.posts_attach_drive_items_to_post import (
    _attach_drive_items_to_post,
)

# SSE broadcaster
from app.realtime.broker import hub


# ---------------------------------------------------------
# POST /api/feed — create post
# ---------------------------------------------------------
@bp.post("")
@bp.post("/")
@login_required
def create_post():
    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}

        # -------------------------------------------------
        # Basic content
        # -------------------------------------------------
        title = (data.get("title") or "").strip()
        html = (data.get("html") or "").strip()

        upload_paths: List[str] = data.get("upload_paths") or []
        drive_items: List[Dict[str, Any]] = data.get("drive_items") or []

        # -------------------------------------------------
        # Audience (permissions)
        # -------------------------------------------------
        raw_type = (data.get("audience_type") or "all").strip()
        audience_type = raw_type if raw_type in ("all", "users", "sector") else "all"
        audience_id = data.get("audience_id")

        raw_allowed = data.get("allowed_user_ids") or []
        if not isinstance(raw_allowed, list):
            raw_allowed = []

        allowed_user_ids: List[int] = []
        for v in raw_allowed:
            try:
                uid = int(v)
                if uid not in allowed_user_ids:
                    allowed_user_ids.append(uid)
            except Exception:
                # ignore invalid ids
                continue

        # -------------------------------------------------
        # Empty post protection
        # -------------------------------------------------
        if not title and not html and not upload_paths and not drive_items:
            return jsonify({"error": "Empty content"}), 400

        # -------------------------------------------------
        # Create Post
        # -------------------------------------------------
        p_fields: Dict[str, Any] = dict(
            author_id=current_user.id,
            title=title or None,
            html=html or None,
            audience_type=audience_type,
            audience_id=int(audience_id) if audience_id else None,
        )

        if _has_col(FeedPost, "is_deleted"):
            p_fields["is_deleted"] = False

        p = FeedPost(**p_fields)
        db.session.add(p)
        db.session.flush()  # need p.id for attachments

        # -------------------------------------------------
        # Attachments
        # -------------------------------------------------
        _attach_local_uploads_to_post(p, upload_paths, current_user.id)
        _attach_drive_items_to_post(p, drive_items, current_user.id)

        # -------------------------------------------------
        # Audience restrictions (per-user visibility)
        # -------------------------------------------------
        if p.audience_type == "users":

            def add_user(uid: int) -> None:
                try:
                    db.session.add(
                        FeedPostAllowedUser(post_id=p.id, user_id=uid)
                    )
                except Exception:
                    current_app.logger.exception(
                        "Failed inserting FeedPostAllowedUser post=%s user=%s",
                        p.id,
                        uid,
                    )

            # Author always included
            add_user(current_user.id)

            # Add selected users
            for uid in allowed_user_ids:
                if uid != current_user.id:
                    add_user(uid)

        # -------------------------------------------------
        # Finalize DB
        # -------------------------------------------------
        db.session.commit()

        # Serialize for frontend
        serialized = _post_to_dict(p, with_rel=True, u=current_user)

        # -------------------------------------------------
        # SSE realtime event
        #   app/realtime/api.py listens via hub.poll(...)
        #   and sends:
        #       event: feed_events
        #       data: {"channel":"feed_events","type":"feed:new_post", ...}
        # -------------------------------------------------
        try:
            hub.publish(
                {
                    "channel": "feed_events",
                    "type": "feed:new_post",
                    "post": serialized,
                }
            )
        except Exception:
            # Realtime failure must NOT break post creation
            current_app.logger.exception("Failed to publish feed:new_post SSE event")

        return jsonify(serialized), 201

    except Exception as e:
        current_app.logger.exception("create_post failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
