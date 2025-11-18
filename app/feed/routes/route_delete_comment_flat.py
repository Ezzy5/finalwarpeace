# app/feed/routes/route_delete_comment_flat.py
from __future__ import annotations
from datetime import datetime
from flask import jsonify, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from flask import current_app
from app.feed import bp
from app.feed.models import FeedComment
from app.feed.routes.comments_get_comment_flat import _get_comment_flat
from app.feed.routes.util_can_edit_comment import _can_edit_comment
from app.feed.routes.util_has_col import _has_col

@bp.route("/comments/<int:comment_id>", methods=["DELETE", "POST"])
@login_required
def delete_comment_flat(comment_id: int):
    # Allow POST with X-HTTP-Method-Override: DELETE
    if request.method == "POST" and (request.headers.get("X-HTTP-Method-Override","").upper() != "DELETE"):
        abort(405)

    c = _get_comment_flat(comment_id)
    if not c:
        return jsonify({"error": "Not found"}), 404
    if not _can_edit_comment(current_user, c):
        return jsonify({"error": "Forbidden"}), 403

    if _has_col(FeedComment, "is_deleted"):
        c.is_deleted = True
        if _has_col(FeedComment, "updated_at"):
            c.updated_at = datetime.utcnow()
        db.session.commit()
    else:
        db.session.delete(c)
        db.session.commit()
    return jsonify({"ok": True}), 200
