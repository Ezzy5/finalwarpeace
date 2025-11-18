# app/callendar/routes/api.py
from __future__ import annotations
import os
from datetime import datetime, timezone  # keep timezone imported
from typing import Any, Dict, List, Optional

from flask import jsonify, request, current_app, send_file, abort
from flask_login import login_required, current_user
from werkzeug.datastructures import FileStorage
from sqlalchemy import or_

from app.utils.tz import to_utc_naive, iso_utc_z, app_tz  # ✅ our tz helpers

from .. import bp
# Kept for compatibility if referenced elsewhere:
from ..forms import EventForm, FilterForm  # noqa: F401
from ..models import Event, RepeatType, InviteStatus
from ..utils import calc_period_bounds
from ..services.calendar_service import (
    create_event,
    update_event,
    delete_event,
    get_event,
    get_events_for_user,
    expand_event_instances,
)
from ..services.invitations_service import (
    list_invitations_for_user,
    respond_to_invitation,
    get_invitation_map_for_events,
)
from ..integration.tickets_adapter import fetch_ticket_blocks_for_calendar

# ✅ Hooks (all notifications live here)
from ..notify_hooks import (
    on_event_created,
    on_event_updated,
    on_event_rsvp,
)

# User model for attendees Select2 endpoint
try:
    from app.models import User
except Exception:
    User = None  # type: ignore


# -------------------------
# Helpers
# -------------------------

def _display_name(u: User) -> str:
    full = getattr(u, "full_name", None)
    if full:
        return full
    first = (getattr(u, "first_name", None) or "").strip()
    last = (getattr(u, "last_name", None) or "").strip()
    if first or last:
        return f"{first} {last}".strip()
    username = getattr(u, "username", None)
    if username:
        return username
    email = getattr(u, "email", None)
    if email:
        return email
    return f"user-{getattr(u, 'id', '')}"


def _to_naive_utc(dt: datetime) -> datetime:
    return to_utc_naive(dt)


def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None

    s = dt_str.strip().replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(s)
        return to_utc_naive(dt)
    except Exception:
        pass

    try:
        dt_local = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        dt_local = dt_local.replace(tzinfo=app_tz())
        return to_utc_naive(dt_local)
    except Exception:
        return None


def _repeat_from_str(val: Optional[str]) -> RepeatType:
    if not val:
        return RepeatType.NONE
    key = val.upper()
    return RepeatType[key] if key in RepeatType.__members__ else RepeatType.NONE


def _invite_status_from_str(val: str) -> InviteStatus:
    key = (val or "").upper()
    if key not in InviteStatus.__members__:
        raise ValueError("Invalid invitation status")
    return InviteStatus[key]


def _collect_reminders(predef: Optional[str], custom: Optional[int]) -> List[int]:
    if custom and int(custom) > 0:
        return [int(custom)]
    if predef:
        try:
            mins = int(predef)
            return [mins] if mins > 0 else []
        except Exception:
            return []
    return []


def _iso_utc_string(dt: datetime) -> str:
    if dt.tzinfo is None:
        return iso_utc_z(dt.replace(tzinfo=timezone.utc))
    return iso_utc_z(dt)


# -------------------------
# API: events CRUD
# -------------------------

@bp.route("/api/events", methods=["GET"])
@login_required
def api_events():
    try:
        start = _parse_iso(request.args.get("start"))
        end = _parse_iso(request.args.get("end"))
        q = request.args.get("q", None)

        role_filters = {
            "show_invitations": request.args.get("invitations") == "1",
            "i_am_organiser": request.args.get("organiser") == "1",
            "i_am_participant": request.args.get("participant") == "1",
            "i_declined": request.args.get("declined") == "1",
        }

        if not (start and end):
            period = request.args.get("period", "THIS_MONTH")
            try:
                next_n = int(request.args.get("next_n_days") or "0")
            except Exception:
                next_n = 0
            local_now = datetime.now(app_tz())
            start_calc, end_calc = calc_period_bounds(period, local_now, next_n)
            start = _to_naive_utc(start_calc)
            end = _to_naive_utc(end_calc)
        else:
            start = _to_naive_utc(start)
            end = _to_naive_utc(end)

        events = get_events_for_user(
            user_id=current_user.id,
            start=start,
            end=end,
            q=q,
            role_filters=role_filters,
        )

        instances: List[Dict[str, Any]] = []
        for ev in events:
            try:
                for s, e, eid in expand_event_instances(
                    ev,
                    window_start=start or datetime.min,
                    window_end=end or datetime.max,
                ):
                    s = _to_naive_utc(s)
                    e = _to_naive_utc(e)
                    instances.append(
                        {
                            "type": "event",
                            "id": eid,
                            "base_event_id": ev.id,
                            "title": ev.title,
                            "description": ev.description,
                            "start_dt": _iso_utc_string(s),
                            "end_dt": _iso_utc_string(e),
                            "timezone": ev.timezone,
                            "repeat": ev.repeat.value if ev.repeat else RepeatType.NONE.value,
                            "organiser_id": ev.organiser_id,
                            "notify_on_responses": ev.notify_on_responses,
                            "attachment_path": ev.attachment_path,
                        }
                    )
            except Exception as row_ex:
                current_app.logger.error(
                    "api_events: expand failed for event id=%s: %s",
                    getattr(ev, "id", "?"),
                    row_ex,
                )

        include_tickets = request.args.get("include_tickets", "1") != "0"
        if include_tickets:
            try:
                ticket_blocks = fetch_ticket_blocks_for_calendar(
                    current_user_id=current_user.id,
                    window_start=start,
                    window_end=end,
                    search_q=q,
                )
                for tb in (ticket_blocks or []):
                    s = tb.get("start_dt")
                    e = tb.get("end_dt")
                    if isinstance(s, datetime):
                        tb["start_dt"] = _iso_utc_string(_to_naive_utc(s))
                    if isinstance(e, datetime):
                        tb["end_dt"] = _iso_utc_string(_to_naive_utc(e))
                instances.extend(ticket_blocks or [])
            except Exception:
                current_app.logger.exception("api_events: tickets fetch failed")

        try:
            inv_map = get_invitation_map_for_events([ev.id for ev in events], current_user.id)
            inv_payload = {str(k): v.value for k, v in inv_map.items()}
        except Exception as im_ex:
            current_app.logger.error("api_events: invitation map failed: %s", im_ex)
            inv_payload = {}

        return jsonify({"items": instances, "invitation_map": inv_payload})

    except Exception:
        current_app.logger.exception("api_events: unhandled error")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/events", methods=["POST"])
@login_required
def api_create_event():
    """
    Create an event. Accepts form-data (for file) or JSON.
    Fields:
      title, description, start_dt, end_dt, timezone, repeat,
      attendees (list[int]), notify_on_responses (bool),
      reminder / reminder_predefined (str), reminder_custom (int), attachment (file)
    """
    try:
        is_form = bool(request.files) or (request.content_type or "").startswith("multipart/form-data")
        data = request.form if is_form else (request.json or {})

        title = (data.get("title") or "").strip()
        start_dt = _parse_iso(data.get("start_dt"))
        end_dt = _parse_iso(data.get("end_dt"))
        timezone_val = (data.get("timezone") or None) or None
        description = (data.get("description") or "").strip() or None
        repeat = _repeat_from_str(data.get("repeat"))

        # ✅ DEFAULT to True unless explicitly falsey (matches your expectation)
        notify_raw = (data.get("notify_on_responses", "1"))
        notify = str(notify_raw).lower() in {"1", "true", "yes", "on"}

        if is_form:
            attendees_raw = request.form.getlist("attendees")
            attendees = [int(x) for x in attendees_raw if str(x).strip().isdigit()]
        else:
            att_val = data.get("attendees") or []
            if isinstance(att_val, str):
                attendees = [int(x) for x in att_val.split(",") if x.strip().isdigit()]
            else:
                attendees = [int(x) for x in att_val]

        predef = data.get("reminder") or data.get("reminder_predefined")
        custom_val = data.get("reminder_custom")
        custom_int = int(custom_val) if custom_val not in (None, "", []) else None
        reminders = _collect_reminders(predef, custom_int)

        file_obj: Optional[FileStorage] = request.files.get("attachment") if is_form else None

        if not title or not start_dt or not end_dt:
            return jsonify({"error": "Missing required fields (title, start_dt, end_dt)."}), 400

        organiser_name = None
        try:
            name = ""
            full = getattr(current_user, "full_name", None) or ""
            if full.strip():
                name = full.strip()
            else:
                fn = (getattr(current_user, "first_name", "") or "").strip()
                ln = (getattr(current_user, "last_name", "") or "").strip()
                combo = f"{fn} {ln}".strip()
                if combo:
                    name = combo
                else:
                    name = (getattr(current_user, "username", None) or getattr(current_user, "email", "") or "").strip()
            organiser_name = name or None
        except Exception:
            organiser_name = None

        ev = create_event(
            title=title,
            start_dt=start_dt,
            end_dt=end_dt,
            organiser_id=current_user.id,
            description=description,
            timezone=timezone_val,
            repeat=repeat,
            notify_on_responses=notify,  # ✅ default True unless explicitly disabled
            attendees_user_ids=attendees,
            reminder_minutes_list=reminders,
            attachment_file=file_obj,
        )

        try:
            if hasattr(ev, "organiser_name") and not (ev.organiser_name and ev.organiser_name.strip()):
                ev.organiser_name = organiser_name or ""
                from app.extensions import db  # local import
                db.session.commit()
        except Exception:
            current_app.logger.exception("api_create_event: failed to set organiser_name")

        try:
            on_event_created(ev)
        except Exception:
            current_app.logger.exception("api_create_event: on_event_created failed")

        return jsonify({"ok": True, "event": ev.to_dict(include_attendees=True)}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception:
        current_app.logger.exception("api_create_event: unhandled")
        return jsonify({"error": "Failed to create event."}), 500


@bp.route("/api/events/<int:event_id>", methods=["PUT", "PATCH"])
@login_required
def api_update_event(event_id: int):
    try:
        is_form = bool(request.files) or (request.content_type or "").startswith("multipart/form-data")
        data = request.form if is_form else (request.json or {})

        ev_before = get_event(event_id)
        if not ev_before:
            return jsonify({"error": "Not found"}), 404

        class _Snap: ...
        before = _Snap()
        for f in ("title", "start_dt", "end_dt", "description", "location", "timezone"):
            setattr(before, f, getattr(ev_before, f, None))

        kwargs: Dict[str, Any] = {}
        if "title" in data:
            kwargs["title"] = (data.get("title") or "").strip()
        if "description" in data:
            kwargs["description"] = (data.get("description") or "").strip()
        if "start_dt" in data:
            kwargs["start_dt"] = _parse_iso(data.get("start_dt"))
        if "end_dt" in data:
            kwargs["end_dt"] = _parse_iso(data.get("end_dt"))
        if "timezone" in data:
            kwargs["timezone"] = data.get("timezone") or None
        if "repeat" in data:
            kwargs["repeat"] = _repeat_from_str(data.get("repeat"))
        if "notify_on_responses" in data:
            val = data.get("notify_on_responses")
            kwargs["notify_on_responses"] = str(val).lower() in {"1", "true", "yes", "on"}

        if is_form:
            if "attendees" in request.form:
                attendees_raw = request.form.getlist("attendees")
                kwargs["attendees_user_ids"] = [int(x) for x in attendees_raw if str(x).strip().isdigit()]
        else:
            if "attendees" in data:
                att_val = data.get("attendees") or []
                if isinstance(att_val, str):
                    kwargs["attendees_user_ids"] = [int(x) for x in att_val.split(",") if x.strip().isdigit()]
                else:
                    kwargs["attendees_user_ids"] = [int(x) for x in att_val]

        predef = data.get("reminder") or data.get("reminder_predefined")
        custom_val = data.get("reminder_custom")
        if predef is not None or custom_val is not None:
            custom_int = int(custom_val) if custom_val not in (None, "", []) else None
            kwargs["reminder_minutes_list"] = _collect_reminders(predef, custom_int)

        if "attachment" in request.files:
            file_obj: FileStorage = request.files["attachment"]
            kwargs["attachment_file"] = file_obj

        ev = update_event(event_id, **kwargs)

        try:
            on_event_updated(before, ev)
        except Exception:
            current_app.logger.exception("api_update_event: on_event_updated failed")

        return jsonify({"ok": True, "event": ev.to_dict(include_attendees=True)})

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception:
        current_app.logger.exception("api_update_event: unhandled")
        return jsonify({"error": "Failed to update event."}), 500


@bp.route("/api/events/<int:event_id>", methods=["DELETE"])
@login_required
def api_delete_event(event_id: int):
    try:
        delete_event(event_id)
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("api_delete_event: unhandled")
        return jsonify({"error": "Failed to delete event."}), 500


@bp.route("/api/events/<int:event_id>", methods=["GET"])
@login_required
def api_get_event(event_id: int):
    ev = get_event(event_id)
    if not ev:
        return jsonify({"error": "Not found"}), 404

    organiser_name = None
    try:
        if getattr(ev, "organiser_id", None) and User:
            u = User.query.get(int(ev.organiser_id))
            if u:
                organiser_name = _display_name(u)
    except Exception:
        organiser_name = None

    attendees = []
    try:
        if hasattr(ev, "attendees") and ev.attendees:
            for a in ev.attendees:
                u = getattr(a, "user", None) or a
                if not u:
                    continue
                attendees.append({
                    "id": getattr(u, "id", None),
                    "name": _display_name(u),
                    "email": getattr(u, "email", None),
                })
    except Exception:
        pass

    payload = {
        "id": ev.id,
        "title": ev.title,
        "description": ev.description,
        "start_dt": ev.start_dt.isoformat(),
        "end_dt": ev.end_dt.isoformat(),
        "timezone": ev.timezone,
        "repeat": ev.repeat.value if ev.repeat else "NONE",
        "organiser_id": ev.organiser_id,
        "organiser_name": organiser_name,
        "notify_on_responses": ev.notify_on_responses,
        "attachment_path": ev.attachment_path,
        "attendees": attendees,
    }
    return jsonify({"event": payload})


@bp.route("/api/events/<int:event_id>/attachment", methods=["GET"])
@login_required
def api_event_attachment(event_id: int):
    ev = get_event(event_id)
    if not ev or not getattr(ev, "attachment_path", None):
        abort(404)

    path = ev.attachment_path
    if os.path.isabs(path):
        if not os.path.isfile(path):
            abort(404)
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))

    root = current_app.config.get("UPLOAD_FOLDER", current_app.instance_path)
    full = os.path.join(root, path)
    if not os.path.isfile(full):
        abort(404)
    return send_file(full, as_attachment=True, download_name=os.path.basename(full))


# -------------------------
# API: invitations
# -------------------------

@bp.route("/api/invitations", methods=["GET"])
@login_required
def api_list_invitations():
    try:
        invitations = list_invitations_for_user(current_user.id)
        items = []
        for inv in invitations:
            ev = inv.event
            try:
                s = _to_naive_utc(ev.start_dt)
                e = _to_naive_utc(ev.end_dt)
                items.append(
                    {
                        "event_id": ev.id,
                        "event_title": ev.title,
                        "start_dt": _iso_utc_string(s),
                        "end_dt": _iso_utc_string(e),
                        "organiser_id": ev.organiser_id,
                        "status": inv.status.value,
                    }
                )
            except Exception as row_ex:
                current_app.logger.error(
                    "api_list_invitations: bad row event id=%s: %s",
                    getattr(ev, "id", "?"),
                    row_ex,
                )
        return jsonify({"items": items})
    except Exception:
        current_app.logger.exception("api_list_invitations: unhandled")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/invitations/respond", methods=["POST"])
@login_required
def api_respond_invitation():
    data = request.json or request.form or {}
    try:
        event_id = int(data.get("event_id"))
        status = _invite_status_from_str(data.get("status"))
    except Exception:
        return jsonify({"error": "Invalid payload."}), 400

    try:
        ea = respond_to_invitation(event_id=event_id, user_id=current_user.id, status=status)

        # 🔔 Notify organiser (respects notify_on_responses default=True)
        try:
            ev = get_event(event_id)
            if ev:
                on_event_rsvp(ev, current_user, status.value)
        except Exception:
            current_app.logger.exception("Failed to run on_event_rsvp")

        # Return fresh list & counters
        try:
            items = list_invitations_for_user(current_user.id)
            inv_payload = []
            for inv in (items or []):
                ev2 = inv.event
                inv_payload.append({
                    "event_id": ev2.id,
                    "event_title": ev2.title,
                    "start_dt": ev2.start_dt.isoformat(),
                    "end_dt": ev2.end_dt.isoformat(),
                    "organiser_id": ev2.organiser_id,
                    "status": inv.status.value,
                })
        except Exception:
            inv_payload = []

        try:
            inv_count = len(inv_payload)
        except Exception:
            inv_count = 0

        try:
            from app.notifications.models import Notification
            notif_unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        except Exception:
            notif_unread = 0

        return jsonify({
            "ok": True,
            "invitation": {
                "event_id": ea.event_id,
                "user_id": ea.user_id,
                "status": ea.status.value,
                "responded_at": ea.responded_at.isoformat() if ea.responded_at else None,
            },
            "invitations": {"items": inv_payload, "count": inv_count},
            "notifications": {"unread": notif_unread}
        })
    except Exception:
        current_app.logger.exception("Failed responding to invitation")
        return jsonify({"error": "Failed to update invitation."}), 500


# -------------------------
# API: users options (Select2)
# -------------------------

@bp.route("/api/users/options", methods=["GET"])
@login_required
def api_users_options():
    try:
        from app.models import User  # adjust if your User model lives elsewhere
    except Exception:
        return jsonify({"results": []})

    q = (request.args.get("q") or "").strip()
    qry = User.query

    if q:
        like = f"%{q}%"
        ors = []
        if hasattr(User, "username"):   ors.append(User.username.ilike(like))
        if hasattr(User, "email"):      ors.append(User.email.ilike(like))
        if hasattr(User, "full_name"):  ors.append(User.full_name.ilike(like))
        if hasattr(User, "first_name"): ors.append(User.first_name.ilike(like))
        if hasattr(User, "last_name"):  ors.append(User.last_name.ilike(like))
        if ors:
            qry = qry.filter(or_(*ors))

    rows = qry.order_by(User.id.desc()).limit(30).all()

    def label(u) -> str:
        name = (
            getattr(u, "full_name", None)
            or " ".join([getattr(u, "first_name", "") or "", getattr(u, "last_name", "") or ""]).strip()
            or getattr(u, "username", None)
            or f"user-{getattr(u, 'id', '')}"
        )
        email = getattr(u, "email", None)
        return f"{name} <{email}>" if email else name

    return jsonify({"results": [{"id": getattr(u, "id", None), "text": label(u)} for u in rows]})


@bp.route("/api/invitations/count", methods=["GET"])
@login_required
def api_invitations_count():
    items = list_invitations_for_user(current_user.id)
    return jsonify({"count": len(items or [])})


# -------------------------
# DEBUG: simulate RSVP (admin/dev)
# -------------------------

@bp.route("/api/debug/rsvp", methods=["POST"])
@login_required
def api_debug_rsvp():
    """
    Body: { "event_id": 123, "status": "ACCEPTED" | "DECLINED" | "TENTATIVE" }
    Forces the RSVP hook to notify the organiser (useful to verify notifications pipeline).
    """
    try:
        payload = request.get_json(silent=True) or {}
        event_id = int(payload.get("event_id"))
        status = _invite_status_from_str(payload.get("status") or "ACCEPTED")
        ev = get_event(event_id)
        if not ev:
            return jsonify({"error": "Event not found"}), 404
        on_event_rsvp(ev, current_user, status.value)
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("api_debug_rsvp: failed")
        return jsonify({"error": "debug rsvp failed"}), 500
