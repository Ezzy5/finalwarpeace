# app/feed/routes/route_get_post_comments.py
from __future__ import annotations
from flask import jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost, FeedComment
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.perms_can_view_post import _can_view_post
from app.feed.routes.serializers_comment_to_dict import _comment_to_dict

@bp.get("/<int:post_id>/comments")
@login_required
def get_post_comments(post_id: int):
    """Return all comments for a specific feed post."""
    try:
        # --- verify post exists and can be viewed ---
        post = db.session.get(FeedPost, post_id)
        if not post:
            return jsonify({"error": "Not found"}), 404
        if _has_col(FeedPost, "is_deleted") and getattr(post, "is_deleted", False):
            return jsonify({"error": "Not found"}), 404
        if not _can_view_post(current_user, post):
            return jsonify({"error": "Forbidden"}), 403

        # --- fetch comments ---
        q = db.session.query(FeedComment).filter_by(post_id=post.id)
        if _has_col(FeedComment, "is_deleted"):
            q = q.filter(FeedComment.is_deleted.is_(False))
        comments = q.order_by(FeedComment.created_at.asc()).all()

        return jsonify({
            "items": [_comment_to_dict(c, with_rel=True, u=current_user) for c in comments]
        })
    except Exception as e:
        current_app.logger.exception("get_post_comments failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
