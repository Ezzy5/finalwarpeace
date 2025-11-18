# app/feed/routes/route_pin_toggle.py
from __future__ import annotations
from datetime import datetime
from flask import request, jsonify
from flask_login import login_required, current_user
from flask import current_app
from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost, FeedPinnedPost
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.perms_can_view_post import _can_view_post

@bp.post("/<int:post_id>/pin")
@login_required
def pin_toggle(post_id: int):
    """
    Set or toggle pin for current user.
    Body: { "pinned": true|false }  -> explicit set
    Body omitted -> toggle
    """
    try:
        p = db.session.get(FeedPost, post_id)
        if not p:
            return jsonify({"error": "Not found"}), 404
        if _has_col(FeedPost, "is_deleted") and getattr(p, "is_deleted", False):
            return jsonify({"error": "Not found"}), 404
        if not _can_view_post(current_user, p):
            return jsonify({"error": "Forbidden"}), 403

        desired = None
        data = request.get_json(silent=True) or {}
        if "pinned" in data:
            desired = bool(data["pinned"])

        existing = FeedPinnedPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()

        if desired is None:  # toggle
            if existing:
                db.session.delete(existing)
                pinned = False
            else:
                db.session.add(FeedPinnedPost(user_id=current_user.id, post_id=post_id, created_at=datetime.utcnow()))
                pinned = True
        else:  # explicit set
            if desired and not existing:
                db.session.add(FeedPinnedPost(user_id=current_user.id, post_id=post_id, created_at=datetime.utcnow()))
                pinned = True
            elif (not desired) and existing:
                db.session.delete(existing)
                pinned = False
            else:
                pinned = desired

        db.session.commit()
        return jsonify({"ok": True, "pinned": pinned})
    except Exception as e:
        current_app.logger.exception("pin_toggle failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
