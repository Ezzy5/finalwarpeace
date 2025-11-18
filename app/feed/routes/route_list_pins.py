# app/feed/routes/route_list_pins.py
from __future__ import annotations
from flask import jsonify
from flask_login import login_required, current_user
from flask import current_app
from app.feed import bp
from app.feed.models import FeedPost, FeedPinnedPost
from app.feed.routes.perms_can_view_post import _can_view_post
from app.feed.routes.serializers_post_to_dict import _post_to_dict

@bp.get("/pins")
@login_required
def list_pins():
    """Your pinned posts, newest pin first."""
    try:
        pins = (FeedPinnedPost.query
                .filter_by(user_id=current_user.id)
                .order_by(FeedPinnedPost.created_at.desc())
                .all())
        post_ids = [p.post_id for p in pins]
        if not post_ids:
            return jsonify({"items": []})
        posts = FeedPost.query.filter(FeedPost.id.in_(post_ids)).all()
        by_id = {p.id: p for p in posts}
        ordered_posts = [by_id.get(pid) for pid in post_ids if by_id.get(pid)]
        ordered_posts = [p for p in ordered_posts if _can_view_post(current_user, p)]
        return jsonify({"items": [_post_to_dict(p, with_rel=True, u=current_user) for p in ordered_posts]})
    except Exception as e:
        current_app.logger.exception("list_pins failed")
        return jsonify({"items": [], "error": "internal", "detail": str(e)}), 500
