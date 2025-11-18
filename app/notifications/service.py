# app/notifications/service.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
from flask import current_app
from app.extensions import db
from .models import Notification

# -------------------------------------------------------------------
# Templates for body text built from meta["type"]
# -------------------------------------------------------------------
TEMPLATES: Dict[str, str] = {
    "event_invite":    "📅 Покана: „{title}“ од {organiser_name}.",
    "event_updated":   "✏️ Ажурирање на настан: „{title}“. Изменето: {changed_fields_display}.",
    "event_reminder":  "🔔 Your event starts in {reminder_minutes} min.",
    "event_rsvp":      "🟢 {actor} одговори: {response_display} за „{title}“.",
    "generic":         "ℹ️ {message}",
}

RESPONSE_DISPLAY = {
    "ACCEPTED":  "ПРИФАТЕН",
    "DECLINED":  "ОДБИЕН",
    "TENTATIVE": "ПРИВРЕМЕН",
}

# Map meta["type"] -> kind string stored in DB
# (You can keep them the same to avoid confusion.)
KIND_MAP: Dict[str, str] = {
    "event_invite":   "event_invite",
    "event_updated":  "event_updated",
    "event_reminder": "event_reminder",
    "event_rsvp":     "event_rsvp",
    "generic":        "generic",
}


def _safe_join(items: Optional[List[str]], sep: str = ", ") -> str:
    if not items:
        return "—"
    return sep.join([str(x) for x in items if str(x).strip()])


def _clean(value: Any) -> str:
    """Coerce None to empty string; avoid 'None' appearing in output."""
    return "" if value is None else str(value)


def _derive_kind(meta: Optional[Dict[str, Any]] = None, fallback: Optional[str] = None) -> str:
    """
    Decide which 'kind' to store:
      - Prefer meta["type"] if it maps to KIND_MAP
      - else use 'fallback' if provided
      - else 'generic'
    """
    t = str((meta or {}).get("type") or "").strip()
    if t and t in KIND_MAP:
        return KIND_MAP[t]
    if fallback:
        fb = fallback.strip()
        if fb:
            return fb
    return "generic"


def render_context_text(meta: Dict[str, Any]) -> str:
    """
    Build the human-readable body from meta and TEMPLATES.
    """
    m = {k: ("" if v is None else v) for k, v in dict(meta or {}).items()}
    typ = str(m.get("type") or "generic")

    if typ == "event_updated":
        changed = m.get("changed_fields")
        m["changed_fields_display"] = _safe_join(list(changed) if isinstance(changed, (list, tuple)) else None)

    if typ == "event_rsvp":
        resp = str(m.get("response") or "").upper()
        m["response_display"] = RESPONSE_DISPLAY.get(resp, resp or "—")

    defaults = {
        "actor": "",
        "title": "",
        "organiser_name": "",
        "message": "",
        "changed_fields_display": "—",
        "reminder_minutes": "",
        "response_display": "",
    }
    for k, v in defaults.items():
        m.setdefault(k, v)

    tmpl = TEMPLATES.get(typ) or TEMPLATES["generic"]
    try:
        text = tmpl.format(**{k: _clean(v) for k, v in m.items()})
        return text[:1].upper() + text[1:] if text else ""
    except Exception as e:
        try:
            current_app.logger.warning("Notification render failed: %s (meta=%r)", e, meta)
        except Exception:
            pass
        return ""


def create_notification(
    *,
    user_id: int,
    title: str,
    body: Optional[str] = None,
    link_url: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    kind: Optional[str] = None,
    commit: bool = True,
) -> Notification:
    """
    Create a notification. Guarantees a non-empty 'kind'.
    - If 'body' not given, it will be rendered from 'meta' using TEMPLATES.
    - 'kind' is derived from meta['type'] unless explicitly provided.
    """
    meta = dict(meta or {})
    rendered_text = (body.strip() if body else "") or render_context_text(meta)
    kind_val = _derive_kind(meta, fallback=(kind or None))

    n = Notification(
        user_id=user_id,
        kind=kind_val,  # ✅ never NULL
        title=(title or "Нотификација").strip(),
        body=(rendered_text or None),
        link_url=(link_url or None),
        meta=(meta or None),
        is_read=False,
    )
    db.session.add(n)
    if commit:
        db.session.commit()
    return n
