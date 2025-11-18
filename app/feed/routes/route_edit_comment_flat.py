# app/feed/routes/route_edit_comment_flat.py
from __future__ import annotations
from datetime import datetime
from flask import request, jsonify, abort
from flask_login import login_required, current_user
from app.extensions import db
from flask import current_app
from app.feed import bp
from app.feed.models import FeedComment
from app.feed.routes.comments_get_comment_flat import _get_comment_flat
from app.feed.routes.comments_serialize_comment import _serialize_comment
from app.feed.routes.util_can_edit_comment import _can_edit_comment
from app.feed.routes.util_has_col import _has_col

@bp.route("/comments/<int:comment_id>", methods=["PATCH", "POST"])
@login_required
def edit_comment_flat(comment_id: int):
    # Allow POST with X-HTTP-Method-Override: PATCH
    if request.method == "POST" and (request.headers.get("X-HTTP-Method-Override","").upper() != "PATCH"):
        abort(405)

    c = _get_comment_flat(comment_id)
    if not c:
        return jsonify({"error": "Not found"}), 404
    if _has_col(FeedComment, "is_deleted") and getattr(c, "is_deleted", False):
        return jsonify({"error": "Not found"}), 404
    if not _can_edit_comment(current_user, c):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    new_html = (data.get("html") or "").strip()
    if not new_html:
        return jsonify({"error": "html required"}), 400

    c.html = new_html
    if _has_col(FeedComment, "updated_at"):
        c.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_serialize_comment(c)), 200
