# app/feed/routes/route_delete_post.py
from __future__ import annotations
from datetime import datetime
from flask import jsonify, request, abort
from flask_login import login_required, current_user
from flask import current_app
from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.util_can_edit_post import _can_edit_post

@bp.route("/<int:post_id>", methods=["DELETE", "POST"])
@login_required
def delete_post(post_id: int):
    # Allow POST with X-HTTP-Method-Override: DELETE
    if request.method == "POST" and (request.headers.get("X-HTTP-Method-Override","").upper() != "DELETE"):
        abort(405)

    p = db.session.get(FeedPost, post_id)
    if not p:
        return jsonify({"error": "Not found"}), 404
    if _has_col(FeedPost, "is_deleted") and getattr(p, "is_deleted", False):
        # already deleted
        return jsonify({"ok": True}), 200
    if not _can_edit_post(current_user, p):
        return jsonify({"error": "Forbidden"}), 403

    if _has_col(FeedPost, "is_deleted"):
        p.is_deleted = True
        if _has_col(FeedPost, "updated_at"):
            p.updated_at = datetime.utcnow()
        db.session.commit()
    else:
        db.session.delete(p)
        db.session.commit()

    return jsonify({"ok": True}), 200
