# app/callendar/routes/cron.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from flask import jsonify, abort, request, current_app
from flask_login import login_required, current_user

from app.callendar import bp
from app.callendar.reminders import enqueue_due_reminders, _utcnow_naive  # internal timing (UTC-naive)

# Use your real helper if available
try:
    from app.permissions import is_admin_like
except Exception:
    def is_admin_like(u): return getattr(u, "id", None) == 1

# Optional: use your existing services for creating events
try:
    from app.callendar.services.calendar_service import create_event
    from app.callendar.models import Event, RepeatType
except Exception:
    create_event = None  # type: ignore
    Event = None         # type: ignore
    class RepeatType:    # minimal fallback
        NONE = "NONE"


def _app_tz_name() -> str:
    try:
        return current_app.config.get("APP_TIMEZONE", "Europe/Skopje")
    except Exception:
        return "Europe/Skopje"

def _app_tz() -> ZoneInfo:
    return ZoneInfo(_app_tz_name())

def _iso_local_from_utc_naive(dt_utc_naive: datetime) -> str:
    """Render a naive UTC datetime as Europe/Skopje ISO string."""
    tz = _app_tz()
    return dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(tz).isoformat()


@bp.route("/cron/run-reminders", methods=["POST"])
@login_required
def cron_run_reminders():
    if not is_admin_like(current_user):
        abort(403)

    data = request.get_json(silent=True) or {}
    horizon = int(data.get("horizon", 120))
    skew = int(data.get("skew", 75))
    catchup = int(data.get("catchup", 180))

    sent = enqueue_due_reminders(
        scan_horizon_minutes=horizon,
        skew_seconds=skew,
        catchup_seconds=catchup,
    )
    return jsonify({"ok": True, "sent": sent})


# --- DEBUG: Show only Skopje local time -------------------------------------

@bp.route("/cron/debug-time", methods=["POST"])
@login_required
def cron_debug_time():
    if not is_admin_like(current_user):
        abort(403)

    tz = _app_tz()
    now_local = datetime.now(tz)
    return jsonify({
        "app_timezone": str(tz),
        "now_local": now_local.isoformat(),   # e.g. 2025-10-15T14:05:23+02:00
    })


# --- DEBUG: Create a test event 6 minutes from now with a 5-min reminder -----

@bp.route("/cron/debug-create-event", methods=["POST"])
@login_required
def cron_debug_create_event():
    if not is_admin_like(current_user):
        abort(403)
    if create_event is None:
        return jsonify({"error": "calendar_service.create_event not available"}), 500

    tz = _app_tz()
    now_local = datetime.now(tz)
    start_local = now_local + timedelta(minutes=6)
    end_local = start_local + timedelta(minutes=30)

    # Convert local -> UTC naive for storage
    start_dt_utc_naive = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_dt_utc_naive = end_local.astimezone(timezone.utc).replace(tzinfo=None)

    title = "DEBUG Reminder Event"
    description = "Auto-created for reminder test."
    reminders = [5]  # fire at start - 5 minutes

    try:
        ev = create_event(
            title=title,
            start_dt=start_dt_utc_naive,
            end_dt=end_dt_utc_naive,
            organiser_id=current_user.id,
            description=description,
            timezone=str(tz),            # optional, display-only field
            repeat=getattr(RepeatType, "NONE", "NONE"),
            notify_on_responses=False,
            attendees_user_ids=[current_user.id],  # you as attendee so you receive reminder
            reminder_minutes_list=reminders,
            attachment_file=None,
        )
        # Set organiser_name if you have that column and it's empty
        try:
            name = (getattr(current_user, "full_name", None)
                    or f"{getattr(current_user,'first_name','') or ''} {getattr(current_user,'last_name','') or ''}".strip()
                    or getattr(current_user, "username", None)
                    or getattr(current_user, "email", None) or "")
            if hasattr(ev, "organiser_name") and not (getattr(ev, "organiser_name") or "").strip():
                from app.extensions import db
                ev.organiser_name = name
                db.session.commit()
        except Exception:
            current_app.logger.exception("debug-create: failed to set organiser_name")
    except Exception:
        current_app.logger.exception("debug-create: failed to create event")
        return jsonify({"error": "failed to create debug event"}), 500

    # Respond ONLY with local times
    return jsonify({
        "ok": True,
        "event": {
            "id": ev.id,
            "title": ev.title,
            "start_local": start_local.isoformat(),
            "end_local": end_local.isoformat(),
            "reminders": reminders,
        }
    })


# --- DEBUG: Explain why reminders are/aren't due (local-only output) --------

@bp.route("/cron/debug-scan", methods=["POST"])
@login_required
def cron_debug_scan():
    if not is_admin_like(current_user):
        abort(403)

    data = request.get_json(silent=True) or {}
    horizon = int(data.get("horizon", 120))
    skew = int(data.get("skew", 75))
    catchup = int(data.get("catchup", 180))

    tz = _app_tz()
    now_local = datetime.now(tz)
    now_utc_naive = _utcnow_naive()  # internal compare baseline (UTC-naive)
    window_end_naive = now_utc_naive + timedelta(minutes=horizon)

    # Fetch same candidates as the reminder runner
    try:
        from app.callendar.reminders import _get_events_in_window, _per_event_minutes
        events = _get_events_in_window(now_utc_naive, window_end_naive)
    except Exception:
        current_app.logger.exception("debug-scan: failed to fetch events")
        return jsonify({"error": "failed to fetch events"}), 500

    items = []
    for ev in events:
        mins = _per_event_minutes(ev)
        hit_list = []
        for m in mins:
            target_utc_naive = ev.start_dt - timedelta(minutes=m)
            dt_to_target = (now_utc_naive - target_utc_naive).total_seconds()
            abs_diff = abs(dt_to_target)
            due_exact = abs_diff <= skew
            due_catchup = (target_utc_naive < now_utc_naive < ev.start_dt) and (0 < dt_to_target <= catchup)

            hit_list.append({
                "m": m,
                "target_local": _iso_local_from_utc_naive(target_utc_naive),
                "due_exact": due_exact,
                "due_catchup": due_catchup,
            })

        items.append({
            "event_id": getattr(ev, "id", None),
            "title": getattr(ev, "title", None),
            "start_local": _iso_local_from_utc_naive(ev.start_dt),
            "mins": mins,
            "hits": hit_list,
        })

    return jsonify({
        "ok": True,
        "now_local": now_local.isoformat(),
        "window_end_local": _iso_local_from_utc_naive(window_end_naive),
        "horizon_minutes": horizon,
        "skew_seconds": skew,
        "catchup_seconds": catchup,
        "candidates": items
    })

# example debug route
from flask import jsonify
from app.utils.tz import debug_pack_now
@bp.route("/api/tz/debug-now", methods=["GET"])
@login_required
def tz_debug_now():
    return jsonify(debug_pack_now())
