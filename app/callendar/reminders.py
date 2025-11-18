# app/callendar/reminders.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Iterable, Optional
from zoneinfo import ZoneInfo
from flask import current_app

from app.extensions import db
from app.callendar.models import Event  # adjust if needed
from app.callendar.notify import notify_event_reminder
from app.notifications.models import Notification

# Try to import your EventReminder model (optional)
try:
    from app.callendar.models import EventReminder  # if you have it
except Exception:
    EventReminder = None  # type: ignore


# -------- Timezone helpers (local = Europe/Skopje by default) ----------------

def _app_tz() -> ZoneInfo:
    try:
        name = current_app.config.get("APP_TIMEZONE", "Europe/Skopje")
    except Exception:
        name = "Europe/Skopje"
    return ZoneInfo(name)

def _to_local(dt: datetime) -> datetime:
    """Convert any dt (naive=>assume UTC) to local (aware) time for logging/UI."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_app_tz())

def _iso_local(dt: datetime) -> str:
    """ISO string in local time with offset, e.g. 2025-10-15T14:05:23+02:00."""
    return _to_local(dt).isoformat()

def _utcnow_naive() -> datetime:
    """
    Return 'now' as naive UTC.
    We take local-now (Skopje) and convert to UTC, then drop tzinfo
    so comparisons match stored naive UTC datetimes.
    """
    local_now = datetime.now(_app_tz())
    return local_now.astimezone(timezone.utc).replace(tzinfo=None)


# -------- Reminder minutes detection -----------------------------------------

# Relationship names we’ll probe on Event (first one that exists will be used)
_RELATIONSHIP_CANDIDATES = (
    "reminders",
    "event_reminders",
    "reminder_entries",
    "notification_offsets",
)

# Minute column names we’ll probe on each reminder row
_MINUTE_CANDIDATES = (
    "minutes",
    "minutes_before",
    "offset_minutes",
    "delta_minutes",
    "remind_at_minutes",
)

def _coerce_int(v) -> Optional[int]:
    try:
        iv = int(v)
        return iv if iv > 0 else None
    except Exception:
        try:
            fv = float(v)
            iv = int(fv)
            return iv if iv > 0 else None
        except Exception:
            return None

def _gather_minutes_from_rows(event: Event) -> List[int]:
    """
    If reminders are stored as rows (e.g., EventReminder), read them regardless of
    the relationship name or the minute column name.
    """
    # Find which relationship exists on the Event
    rel_obj = None
    for rel_name in _RELATIONSHIP_CANDIDATES:
        rel_obj = getattr(event, rel_name, None)
        if rel_obj is not None:
            break

    minutes: List[int] = []
    if rel_obj is None:
        return minutes

    # rel_obj is usually a list-like of reminder rows
    try:
        for r in list(rel_obj or []):
            found = None
            for col in _MINUTE_CANDIDATES:
                if hasattr(r, col):
                    found = _coerce_int(getattr(r, col))
                    if found is not None:
                        minutes.append(found)
                        break
            # As a last resort, if the model itself only exposes one public int attr:
            if found is None:
                try:
                    # probe __dict__ for any candidate-looking value
                    for k, v in getattr(r, "__dict__", {}).items():
                        if k.startswith("_"):
                            continue
                        iv = _coerce_int(v)
                        if iv:
                            minutes.append(iv)
                            break
                except Exception:
                    pass
    except Exception:
        # If iterating the relation fails, just return empty
        return []

    # de-dup + sort
    uniq = sorted({m for m in minutes if m > 0})
    return uniq

def _per_event_minutes(ev: Event) -> List[int]:
    """
    Robustly get per-event reminder minutes from:
      1) ev.reminder_minutes_list (if present/filled), else
      2) ev.<reminders relationship> rows using common column names.
    """
    # 1) direct list on the event
    direct = getattr(ev, "reminder_minutes_list", None)
    out: List[int] = []
    if direct:
        for v in direct or []:
            iv = _coerce_int(v)
            if iv:
                out.append(iv)
        out = sorted({m for m in out if m > 0})
        if out:
            return out

    # 2) relationship rows
    out = _gather_minutes_from_rows(ev)
    return out


# -------- Event window fetch --------------------------------------------------

def _get_events_in_window(window_start: datetime, window_end: datetime) -> List[Event]:
    """Events with start_dt inside [window_start, window_end] (naive UTC)."""
    return (
        db.session.query(Event)
        .filter(Event.start_dt >= window_start)
        .filter(Event.start_dt <= window_end)
        .all()
    )


# -------- De-dupe (DB portable) ---------------------------------------------

def _recent_reminder_sent(user_id: int, title: str, window_seconds: int = 600) -> bool:
    """
    De-dupe by (user_id, title) within window_seconds.
    Works on SQLite/Postgres without JSON operators.
    """
    since = _utcnow_naive() - timedelta(seconds=window_seconds)
    return (
        db.session.query(Notification)
        .filter(Notification.user_id == int(user_id))
        .filter(Notification.title == title)
        .filter(Notification.created_at >= since)
        .count()
        > 0
    )


# -------- Core runner --------------------------------------------------------

def enqueue_due_reminders(
    now: datetime | None = None,
    scan_horizon_minutes: int = 120,
    skew_seconds: int = 75,
    catchup_seconds: int = 180,
) -> int:
    """
    Fire reminders for events starting within the next `scan_horizon_minutes`.

    For each event minute N in `reminder_minutes_list` or reminder rows, send when:
      • now ≈ (start_dt - N minutes) within ±skew_seconds, OR
      • (catch-up) target < now < start_dt AND (now - target) <= catchup_seconds

    Returns the number of user deliveries attempted.
    """
    now = now or _utcnow_naive()
    horizon_end = now + timedelta(minutes=scan_horizon_minutes)

    try:
        events = _get_events_in_window(now, horizon_end)
    except Exception:
        current_app.logger.exception("reminders: failed to fetch events in window")
        return 0

    # helpful log at the start
    try:
        current_app.logger.info(
            "reminders: candidates=%s window=[%s .. %s]",
            len(events),
            _iso_local(now),
            _iso_local(horizon_end),
        )
    except Exception:
        pass

    fired_total = 0

    for ev in events:
        mins_list = _per_event_minutes(ev)

        # log what we found for this event
        try:
            current_app.logger.info(
                "reminders: event_id=%s title=%r minutes=%s",
                getattr(ev, "id", None),
                getattr(ev, "title", None),
                mins_list,
            )
        except Exception:
            pass

        if not mins_list:
            try:
                current_app.logger.info("reminders: skip event_id=%s (no reminder minutes)", getattr(ev, "id", None))
            except Exception:
                pass
            continue

        for m in mins_list:
            target = ev.start_dt - timedelta(minutes=m)  # both naive UTC
            dt_to_target = (now - target).total_seconds()
            abs_diff = abs(dt_to_target)

            due_exact = abs_diff <= skew_seconds
            due_catchup = (target < now < ev.start_dt) and (0 < dt_to_target <= catchup_seconds)

            if not (due_exact or due_catchup):
                continue

            reminder_title = f"Reminder: {ev.title or 'Event'}"
            # recipients: attendees + organiser
            recips: List[Dict[str, Any]] = []
            for a in getattr(ev, "attendees", []) or []:
                uid = getattr(a, "user_id", None) or (a.get("user_id") if isinstance(a, dict) else None)
                if uid:
                    recips.append({"id": int(uid)})
            if getattr(ev, "organiser_id", None):
                recips.append({"id": int(ev.organiser_id)})

            delivered = 0
            for r in recips:
                uid = int(r["id"])
                if _recent_reminder_sent(uid, reminder_title, window_seconds=600):
                    continue
                notify_event_reminder(ev, recipients=[{"id": uid}], reminder_minutes=m)
                delivered += 1

            fired_total += delivered

            # Log in local (Skopje) time for easier reading
            try:
                current_app.logger.info(
                    "reminders: fired=%s event_id=%s m=%s now_local=%s start_local=%s target_local=%s (exact=%s catchup=%s)",
                    delivered,
                    getattr(ev, "id", None),
                    m,
                    _iso_local(now),
                    _iso_local(ev.start_dt),
                    _iso_local(target),
                    due_exact,
                    due_catchup,
                )
            except Exception:
                pass

    if fired_total == 0:
        try:
            current_app.logger.info(
                "reminders: none due now_local=%s window_end_local=%s",
                _iso_local(now),
                _iso_local(horizon_end),
            )
        except Exception:
            pass

    return fired_total
