from datetime import datetime
from flask import request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc, and_
from app.extensions import db
from . import bp
from .models import FeedNotification

PAGE_SIZE = 25

def _row(n: FeedNotification):
    return {
        "id": n.id,
        "kind": n.kind,
        "post_id": n.post_id,
        "actor_id": n.actor_id,
        "payload": n.payload or {},
        "created_at": n.created_at.isoformat(),
        "seen_at": n.seen_at.isoformat() if n.seen_at else None,
    }

@bp.get("/")
@login_required
def list_notifications():
    # Cursor by ?after_id=...
    after_id = request.args.get("after_id", type=int)
    q = FeedNotification.query.filter(FeedNotification.user_id == current_user.id)\
                              .order_by(desc(FeedNotification.id))
    if after_id:
        q = q.filter(FeedNotification.id < after_id)
    items = q.limit(PAGE_SIZE + 1).all()
    has_more = len(items) > PAGE_SIZE
    items = items[:PAGE_SIZE]
    next_cursor = items[-1].id if has_more else None
    return jsonify({"ok": True, "items": [_row(n) for n in items], "next_after_id": next_cursor})

@bp.get("/unread-count")
@login_required
def unread_count():
    cnt = FeedNotification.query.filter(
        FeedNotification.user_id == current_user.id,
        FeedNotification.seen_at.is_(None)
    ).count()
    return jsonify({"ok": True, "count": cnt})

@bp.post("/mark-seen")
@login_required
def mark_seen():
    data = request.get_json(force=True, silent=True) or {}
    ids = data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "ids required"}), 400
    now = datetime.utcnow()
    FeedNotification.query.filter(
        FeedNotification.user_id == current_user.id,
        FeedNotification.id.in_(ids),
        FeedNotification.seen_at.is_(None)
    ).update({"seen_at": now}, synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True})

@bp.post("/mark-all-seen")
@login_required
def mark_all_seen():
    now = datetime.utcnow()
    FeedNotification.query.filter(
        FeedNotification.user_id == current_user.id,
        FeedNotification.seen_at.is_(None)
    ).update({"seen_at": now}, synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True})
