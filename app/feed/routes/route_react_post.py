# app/feed/routes/route_react_post.py
from __future__ import annotations
from datetime import datetime
from flask import request, jsonify
from flask_login import login_required, current_user
from flask import current_app
from app.extensions import db
from app.feed import bp
from app.feed.models import FeedPost, FeedReaction
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.perms_can_view_post import _can_view_post
from app.feed.routes.reactions_reaction_count import _reaction_count

@bp.post("/<int:post_id>/react")
@login_required
def react_post(post_id: int):
    try:
        p = db.session.get(FeedPost, post_id)
        if not p:
            return jsonify({"error": "Not found"}), 404
        if _has_col(FeedPost, "is_deleted") and getattr(p, "is_deleted", False):
            return jsonify({"error": "Not found"}), 404
        if not _can_view_post(current_user, p):
            return jsonify({"error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        emoji = (data.get("emoji") or "").strip() or "👍"
        if emoji != "👍":
            return jsonify({"error": "Unsupported emoji"}), 400

        existing = FeedReaction.query.filter_by(
            post_id=p.id, user_id=current_user.id, emoji="👍"
        ).first()

        if existing:
            db.session.delete(existing)
            reacted = False
        else:
            db.session.add(FeedReaction(post_id=p.id, user_id=current_user.id, emoji="👍", created_at=datetime.utcnow()))
            reacted = True

        db.session.commit()

        like_count = _reaction_count(p.id)
        return jsonify({"ok": True, "counts": {"👍": like_count}, "reacted": reacted})
    except Exception as e:
        current_app.logger.exception("react_post failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
