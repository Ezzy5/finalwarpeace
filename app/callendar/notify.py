# app/callendar/notify.py
from __future__ import annotations
from typing import Iterable, Mapping, Any, Optional, List, Dict

from flask import current_app

from app.notifications.service import create_notification
from app.callendar.models import Event

try:
    from app.models import User
except Exception:
    User = None  # type: ignore


# ----------------- helpers -----------------

def _event_link_url(event: Event) -> str:
    try:
        return f"/callendar?event_id={int(getattr(event, 'id', 0))}"
    except Exception:
        return "/callendar"

def _recipient_id(recipient: Mapping[str, Any] | Any) -> Optional[int]:
    """Accept dicts with 'id', ORM objects with .id, or plain ints."""
    try:
        if isinstance(recipient, int):
            return int(recipient)
        if isinstance(recipient, dict) and "id" in recipient:
            return int(recipient["id"])
        rid = getattr(recipient, "id", None)
        return int(rid) if rid is not None else None
    except Exception:
        return None

def _norm_recips(recipients: Iterable[Mapping[str, Any] | Any]) -> List[int]:
    """Normalize & de-duplicate user ids."""
    ids: List[int] = []
    for r in recipients or []:
        rid = _recipient_id(r)
        if rid is not None:
            ids.append(rid)
    seen = set()
    out: List[int] = []
    for rid in ids:
        if rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out

def _resolve_organiser_name(event: Event) -> str:
    # prefer event.organiser_name; else lookup User
    name = (getattr(event, "organiser_name", None) or "").strip()
    if name:
        return name
    try:
        if User and getattr(event, "organiser_id", None):
            u = User.query.get(int(event.organiser_id))
            if u:
                full = getattr(u, "full_name", None)
                if full:
                    return full
                fn = (getattr(u, "first_name", "") or "").strip()
                ln = (getattr(u, "last_name", "") or "").strip()
                combo = f"{fn} {ln}".strip()
                if combo:
                    return combo
                if getattr(u, "username", None):
                    return u.username
                if getattr(u, "email", None):
                    return u.email
    except Exception:
        pass
    return ""

def _attendee_users(event: Event, *, include_organiser: bool = False) -> List[Dict[str, int]]:
    out: List[Dict[str, int]] = []
    for a in getattr(event, "attendees", []) or []:
        uid = getattr(a, "user_id", None) or (a.get("user_id") if isinstance(a, dict) else None)
        if uid:
            out.append({"id": int(uid)})
    if include_organiser and getattr(event, "organiser_id", None):
        out.append({"id": int(event.organiser_id)})
    return out

def _create_notification_safe(*, user_id: int, title: str, link_url: str, meta: dict, body: Optional[str] = None) -> None:
    """
    Try several signatures so we don't depend on the exact create_notification args.
    Order:
      1) user_id, title, body, link_url, meta
      2) user_id, title, body, link_url
      3) user_id, title, body
      4) user_id, title, link_url, meta
      5) user_id, title, link_url
      6) user_id, title
    Logs failures but never raises.
    """
    tried = []

    def _attempt(func, desc):
        try:
            func()
            return True
        except TypeError as e:
            tried.append(f"{desc} -> TypeError: {e}")
            return False
        except Exception as e:
            tried.append(f"{desc} -> {type(e).__name__}: {e}")
            return False

    # 1)
    if body and _attempt(lambda: create_notification(user_id=user_id, title=title, body=body, link_url=link_url, meta=meta),
                         "user_id,title,body,link_url,meta"):
        return
    # 2)
    if body and _attempt(lambda: create_notification(user_id=user_id, title=title, body=body, link_url=link_url),
                         "user_id,title,body,link_url"):
        return
    # 3)
    if body and _attempt(lambda: create_notification(user_id=user_id, title=title, body=body),
                         "user_id,title,body"):
        return
    # 4)
    if _attempt(lambda: create_notification(user_id=user_id, title=title, link_url=link_url, meta=meta),
                "user_id,title,link_url,meta"):
        return
    # 5)
    if _attempt(lambda: create_notification(user_id=user_id, title=title, link_url=link_url),
                "user_id,title,link_url"):
        return
    # 6)
    if _attempt(lambda: create_notification(user_id=user_id, title=title),
                "user_id,title"):
        return

    try:
        current_app.logger.error(
            "create_notification failed for user_id=%s title=%r; attempts=%s",
            user_id, title, " | ".join(tried)
        )
    except Exception:
        pass


# ----------------- notifications -----------------

def notify_event_invitation(event: Event, *, recipients: Iterable[Mapping[str, Any] | Any] | None = None) -> None:
    """
    Notify attendees about a new event (NOT the organiser).
    meta.type = "event_invite"
    """
    title = f"Покана: {event.title or 'Настан'}"
    body = "Имате нова покана за настан."
    organiser_name = _resolve_organiser_name(event)
    recips = _norm_recips(recipients if recipients is not None else _attendee_users(event, include_organiser=False))

    base_meta = {
        "type": "event_invite",
        "event_id": int(getattr(event, "id", 0)),
        "title": event.title or "Настан",
        "organiser_name": organiser_name,  # empty string if unknown
        "start_dt": getattr(event, "start_dt", None).isoformat() if getattr(event, "start_dt", None) else None,
        "end_dt": getattr(event, "end_dt", None).isoformat() if getattr(event, "end_dt", None) else None,
        "timezone": getattr(event, "timezone", None) or "",
    }

    for uid in recips:
        _create_notification_safe(
            user_id=uid,
            title=title,
            body=body,
            link_url=_event_link_url(event),
            meta=base_meta,
        )


def notify_event_updated(
    event: Event,
    *,
    recipients: Iterable[Mapping[str, Any] | Any] | None = None,
    changed_fields: Optional[list[str]] = None,
) -> None:
    """
    Notify attendees that an event has been updated.
    meta.type = "event_updated"
    """
    title = f"Ажурирање на настан: {event.title or 'Настан'}"
    changed_fields = changed_fields or []
    body = f"Променето: {', '.join(changed_fields)}" if changed_fields else "Настанот е изменет."
    recips = _norm_recips(recipients if recipients is not None else _attendee_users(event, include_organiser=False))

    base_meta = {
        "type": "event_updated",
        "event_id": int(getattr(event, "id", 0)),
        "title": event.title or "Настан",
        "changed_fields": changed_fields,
        "start_dt": getattr(event, "start_dt", None).isoformat() if getattr(event, "start_dt", None) else None,
        "end_dt": getattr(event, "end_dt", None).isoformat() if getattr(event, "end_dt", None) else None,
        "timezone": getattr(event, "timezone", None) or "",
    }

    for uid in recips:
        _create_notification_safe(
            user_id=uid,
            title=title,
            body=body,
            link_url=_event_link_url(event),
            meta=base_meta,
        )


def notify_event_reminder(
    event: Event,
    *,
    recipients: Iterable[Mapping[str, Any] | Any] | None = None,
    reminder_minutes: int = 15,
) -> None:
    """
    Reminder fired for organiser + attendees.
    meta.type = "event_reminder"
    """
    title = f"Потсетник: {event.title or 'Настан'}"
    minutes_txt = f"{int(reminder_minutes)} мин." if reminder_minutes else "скоро"
    body = f"Настанот започнува {minutes_txt}."

    recips = _norm_recips(recipients if recipients is not None else _attendee_users(event, include_organiser=True))

    base_meta = {
        "type": "event_reminder",
        "event_id": int(getattr(event, "id", 0)),
        "title": event.title or "Настан",
        "minutes": int(reminder_minutes) if reminder_minutes else None,
        "start_dt": getattr(event, "start_dt", None).isoformat() if getattr(event, "start_dt", None) else None,
        "timezone": getattr(event, "timezone", None) or "",
    }

    for uid in recips:
        _create_notification_safe(
            user_id=uid,
            title=title,
            body=body,
            link_url=_event_link_url(event),
            meta=base_meta,
        )
