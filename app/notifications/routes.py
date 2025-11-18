# app/notifications/routes.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple

from flask import jsonify, request, render_template, abort, current_app
from flask_login import login_required, current_user

from . import bp
from .models import Notification
from app.extensions import db


# ---------------------------
# Helpers for SPA vs. reload
# ---------------------------

def _is_fragment_request() -> bool:
    """Detect SPA fragment fetch (XHR with X-Requested-With header)."""
    return request.headers.get("X-Requested-With", "").lower() == "fetch"

def _render_dashboard_with(panel_html: str):
    """Return full dashboard with the given panel injected."""
    return render_template("dashboard.html", initial_panel=panel_html)


# ---------------------------
# HTML (SPA panels)
# ---------------------------

@bp.route("/", methods=["GET"])
@login_required
def index():
    panel = render_template("notifications/index.html")
    if _is_fragment_request():
        return panel
    return _render_dashboard_with(panel)


@bp.route("/<int:nid>", methods=["GET"])
@login_required
def view(nid: int):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first()
    if not n:
        abort(404)
    panel = render_template("notifications/view.html", n=n)
    if _is_fragment_request():
        return panel
    return _render_dashboard_with(panel)


# ---------------------------
# JSON API
# ---------------------------

def _serialize_list(rows: List[Notification]) -> List[Dict[str, Any]]:
    return [n.to_dict() for n in rows]

def _get_pagination() -> Tuple[int, int]:
    def clamp(v, lo, hi): return max(lo, min(hi, v))
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 50))
    except ValueError:
        per_page = 50
    return clamp(page, 1, 999_999), clamp(per_page, 1, 200)


@bp.route("/api/notifications", methods=["GET"])
@login_required
def api_list_notifications():
    only_unread = str(request.args.get("only_unread", "false")).lower() == "true"
    use_pagination = request.args.get("page") or request.args.get("per_page")
    page, per_page = _get_pagination() if use_pagination else (None, None)

    # DEV OVERRIDE: show all notifications when explicitly requested and app is in debug mode
    dev_show_all = current_app.debug and request.args.get("dev_show_all") == "1"

    base_q = Notification.query
    if not dev_show_all:
        base_q = base_q.filter_by(user_id=current_user.id)

    if only_unread:
        base_q = base_q.filter_by(is_read=False)

    base_q = base_q.order_by(Notification.created_at.desc(), Notification.id.desc())

    if use_pagination:
        pagination = base_q.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            "items": _serialize_list(pagination.items),
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages
        })

    # fallback (legacy limit)
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    limit = max(1, min(200, limit))
    rows = base_q.limit(limit).all()
    return jsonify({"items": _serialize_list(rows)})


@bp.route("/api/notifications/count", methods=["GET"])
@login_required
def api_notifications_count():
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"unread": unread})


@bp.route("/api/notifications/<int:nid>/read", methods=["POST"])
@login_required
def api_notifications_mark_read(nid: int):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first()
    if not n:
        return jsonify({"error": "Not found"}), 404
    if not n.is_read:
        n.is_read = True
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_notifications_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------
# TEMP DEBUG (remove later)
# ---------------------------

@bp.route("/api/debug/whoami", methods=["GET"])
@login_required
def api_debug_whoami():
    """Return current user's id and a quick count for fast diagnosis."""
    mine_total = Notification.query.filter_by(user_id=current_user.id).count()
    return jsonify({
        "id": current_user.id,
        "mine_total": mine_total,
        "debug": current_app.debug
    })


@bp.route("/api/debug/create", methods=["POST"])
@login_required
def api_debug_create():
    """Create a sample notification for the *currently logged-in* user."""
    from app.notifications.service import create_notification
    n = create_notification(
        user_id=current_user.id,
        kind="event.response",
        title="Одговор на покана",
        meta={"actor": "Debug", "response": "ACCEPTED", "title": "Debug event"},
    )
    return jsonify({"ok": True, "id": n.id})
