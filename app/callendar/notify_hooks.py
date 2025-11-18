# app/callendar/notify_hooks.py
from __future__ import annotations
from typing import List, Dict, Any, Optional

from flask import current_app

from app.callendar.models import Event
from app.callendar.notify import notify_event_invitation, notify_event_updated
from app.notifications.service import create_notification
from app.extensions import db

try:
    from app.notifications.models import Notification  # expected DB model
except Exception:
    Notification = None  # type: ignore


def _attendee_user_list(event: Event) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for a in getattr(event, "attendees", []) or []:
        uid = getattr(a, "user_id", None) or (a.get("user_id") if isinstance(a, dict) else None)
        if uid:
            out.append({"id": int(uid)})
    return out

def _event_link(event_id: int) -> str:
    try:
        return f"/callendar?event_id={int(event_id)}"
    except Exception:
        return "/callendar"

def _display_name(user) -> str:
    try:
        full = getattr(user, "full_name", None)
        if full: return full
        fn = (getattr(user, "first_name", "") or "").strip()
        ln = (getattr(user, "last_name", "") or "").strip()
        if fn or ln: return f"{fn} {ln}".strip()
        un = getattr(user, "username", None)
        if un: return un
        em = getattr(user, "email", None)
        if em: return em
    except Exception:
        pass
    return "Корисник"

def _fallback_db_notification(*, user_id: int, title: str, link_url: str, meta: dict, body: Optional[str]) -> bool:
    if Notification is None:
        try:
            current_app.logger.error("notify_hooks: Notification model unavailable; cannot fallback DB insert")
        except Exception: pass
        return False
    try:
        n = Notification()  # type: ignore
        if hasattr(n, "user_id"): n.user_id = int(user_id)
        if hasattr(n, "title"): n.title = title
        if body:
            if hasattr(n, "body"): n.body = body
            elif hasattr(n, "context_text"): n.context_text = body
            elif hasattr(n, "message"): n.message = body
        if hasattr(n, "link_url"): n.link_url = link_url
        if hasattr(n, "meta"): n.meta = meta
        if hasattr(n, "is_read"): n.is_read = False
        db.session.add(n)
        db.session.commit()
        try:
            current_app.logger.info("notify_hooks: fallback DB notification inserted (user_id=%s, title=%r)", user_id, title)
        except Exception: pass
        return True
    except Exception as e:
        try:
            current_app.logger.exception("notify_hooks: fallback DB insert failed: %s", e)
        except Exception: pass
        try:
            db.session.rollback()
        except Exception: pass
        return False

def _create_notification_safe(*, user_id: int, title: str, link_url: str, meta: dict, body: Optional[str]) -> bool:
    attempts = []

    def _try(call, label):
        try:
            call()
            return True
        except TypeError as e:
            attempts.append(f"{label} -> TypeError: {e}")
            return False
        except Exception as e:
            attempts.append(f"{label} -> {type(e).__name__}: {e}")
            return False

    # Try rich → minimal signatures
    if body and _try(lambda: create_notification(user_id=user_id, title=title, body=body, link_url=link_url, meta=meta),
                     "user_id,title,body,link_url,meta"): return True
    if body and _try(lambda: create_notification(user_id=user_id, title=title, body=body, link_url=link_url),
                     "user_id,title,body,link_url"): return True
    if body and _try(lambda: create_notification(user_id=user_id, title=title, body=body),
                     "user_id,title,body"): return True
    if _try(lambda: create_notification(user_id=user_id, title=title, link_url=link_url, meta=meta),
            "user_id,title,link_url,meta"): return True
    if _try(lambda: create_notification(user_id=user_id, title=title, link_url=link_url),
            "user_id,title,link_url"): return True
    if _try(lambda: create_notification(user_id=user_id, title=title),
            "user_id,title"): return True

    try:
        current_app.logger.error(
            "notify_hooks: service create_notification failed (user_id=%s title=%r); attempts=%s",
            user_id, title, " | ".join(attempts)
        )
    except Exception: pass

    return _fallback_db_notification(user_id=user_id, title=title, link_url=link_url, meta=meta, body=body)


# ---------- public hooks ----------

def on_event_created(event: Event) -> None:
    recips = _attendee_user_list(event)
    if recips:
        notify_event_invitation(event, recipients=recips)

def on_event_updated(before: Event, after: Event) -> None:
    changed_fields: list[str] = []
    for f in ("title", "start_dt", "end_dt", "description", "location", "timezone"):
        if getattr(before, f, None) != getattr(after, f, None):
            changed_fields.append(f)
    if not changed_fields:
        return
    recips = _attendee_user_list(after)
    if recips:
        notify_event_updated(after, recipients=recips, changed_fields=changed_fields)

def on_event_rsvp(event: Event, user, response: str) -> None:
    # Treat None as True (default ON); only skip if explicitly False
    nor = getattr(event, "notify_on_responses", None)
    notify_yes = (nor is None) or (nor is True)
    if not notify_yes:
        try:
            current_app.logger.info("on_event_rsvp: skip (notify_on_responses=False) event_id=%s", getattr(event, "id", None))
        except Exception: pass
        return

    organiser_id = getattr(event, "organiser_id", None)
    if not organiser_id:
        try:
            current_app.logger.warning("on_event_rsvp: no organiser_id for event_id=%s", getattr(event, "id", None))
        except Exception: pass
        return

    try:
        if int(organiser_id) == int(getattr(user, "id", 0)):
            try:
                current_app.logger.info("on_event_rsvp: organiser self-response; no notify. event_id=%s", getattr(event, "id", None))
            except Exception: pass
            return
    except Exception:
        pass

    username = _display_name(user)
    resp = (response or "").strip().lower()

    if resp == "accepted":
        meta_type = "event_rsvp_accepted"
        body = f"{username} ја прифати поканата за „{event.title or 'Настан'}“."
    elif resp == "declined":
        meta_type = "event_rsvp_declined"
        body = f"{username} ја одби поканата за „{event.title or 'Настан'}“."
    else:
        meta_type = "event_rsvp_tentative"
        body = f"{username} е неизвесен за „{event.title or 'Настан'}“."

    title = f"Одговор на покана: {username} ({resp.upper()})"

    meta = {
        "type": meta_type,
        "event_id": int(getattr(event, "id", 0)),
        "title": event.title or "Настан",
        "response": resp.upper(),
        "user": {"id": getattr(user, "id", None), "name": username},
        "start_dt": getattr(event, "start_dt", None).isoformat() if getattr(event, "start_dt", None) else None,
        "timezone": getattr(event, "timezone", None) or "",
    }

    ok = _create_notification_safe(
        user_id=int(organiser_id),
        title=title,
        body=body,
        link_url=_event_link(getattr(event, "id", 0)),
        meta=meta,
    )

    try:
        current_app.logger.info(
            "on_event_rsvp: sent=%s organiser_id=%s event_id=%s type=%s",
            ok, organiser_id, getattr(event, "id", None), meta.get("type")
        )
    except Exception:
        pass
