# app/feed/routes/route_add_comment.py
from __future__ import annotations
from datetime import datetime
from flask import request, jsonify
from flask_login import login_required, current_user
from flask import current_app
from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost, FeedComment
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.perms_can_view_post import _can_view_post
from app.feed.routes.serializers_safe_author_dict import _safe_author_dict

@bp.post("/<int:post_id>/comments")
@bp.post("/<int:post_id>/comments/")
@login_required
def add_comment(post_id: int):
    try:
        p = db.session.get(FeedPost, post_id)
        if not p:
            return jsonify({"error": "Not found"}), 404
        if _has_col(FeedPost, "is_deleted") and getattr(p, "is_deleted", False):
            return jsonify({"error": "Not found"}), 404
        if not _can_view_post(current_user, p):
            return jsonify({"error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        html = (data.get("html") or "").strip()
        if not html:
            return jsonify({"error": "Empty comment"}), 400

        fields = dict(post_id=post_id, author_id=current_user.id, html=html, created_at=datetime.utcnow())
        if _has_col(FeedComment, "is_deleted"):
            fields["is_deleted"] = False

        c = FeedComment(**fields)
        db.session.add(c)
        db.session.commit()

        return jsonify({
            "id": getattr(c, "id", None),
            "post_id": getattr(c, "post_id", None),
            "html": getattr(c, "html", "") or "",
            "created_at": (getattr(c, "created_at", None) or datetime.utcnow()).isoformat(),
            "updated_at": (getattr(c, "updated_at", None) or getattr(c, "created_at", None) or datetime.utcnow()).isoformat(),
            "author": _safe_author_dict(getattr(c, "author", None)),
        }), 201
    except Exception as e:
        current_app.logger.exception("add_comment failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
