# app/feed/routes/route_get_post.py
from __future__ import annotations
from flask import jsonify
from flask_login import login_required, current_user
from flask import current_app
from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.perms_can_view_post import _can_view_post
from app.feed.routes.serializers_post_to_dict import _post_to_dict

@bp.get("/<int:post_id>")
@login_required
def get_post(post_id: int):
    try:
        p = db.session.get(FeedPost, post_id)
        if not p:
            return jsonify({"error": "Not found"}), 404
        if _has_col(FeedPost, "is_deleted") and getattr(p, "is_deleted", False):
            return jsonify({"error": "Not found"}), 404
        if not _can_view_post(current_user, p):
            return jsonify({"error": "Forbidden"}), 403
        return jsonify(_post_to_dict(p, with_rel=True, u=current_user))
    except Exception as e:
        current_app.logger.exception("get_post failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
