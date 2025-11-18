# app/callendar/routes/ticket_details.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, current_app, url_for
from flask_login import login_required, current_user

from .. import bp

# Soft import; keep route alive even if tickets module is missing
try:
    from app.tickets.models import Ticket  # type: ignore
except Exception:  # pragma: no cover
    Ticket = None  # type: ignore


# ------------------------- helpers -------------------------

def _to_dt(v: Any, *, end: bool = False) -> Optional[datetime]:
    """Convert value to datetime; dates -> start/end of day."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        if end:
            return datetime(v.year, v.month, v.day, 23, 59, 59, 999000)
        return datetime(v.year, v.month, v.day, 0, 0, 0, 0)
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def _get(obj: Any, *names, default=None):
    """Return the first existing attribute/callable result from a list of names."""
    for n in names:
        if hasattr(obj, n):
            try:
                v = getattr(obj, n)
                return v() if callable(v) else v
            except Exception:
                continue
    return default


def _label(x: Any) -> Optional[str]:
    """Return .name/.title or str(x)."""
    if x is None:
        return None
    nm = _get(x, "name", "title")
    return str(nm) if nm else str(x)


def _full_name(u: Any) -> str:
    """Prefer First Last, then full_name, then username/name, then user-<id>."""
    fn = _get(u, "first_name")
    ln = _get(u, "last_name")
    if fn or ln:
        return " ".join([p for p in [fn, ln] if p]).strip()
    full = _get(u, "full_name")
    if full:
        return str(full)
    return _get(u, "name", "username", default=f"user-{_get(u,'id')}") or f"user-{_get(u,'id')}"


def _ticket_url(t: Any) -> str:
    """
    Build a robust URL to the ticket page:
    1) model.get_absolute_url()
    2) url_for on common endpoints
    3) common path patterns
    4) fallback to /tickets
    """
    # 1) model method
    if hasattr(t, "get_absolute_url"):
        try:
            u = t.get_absolute_url()
            if u:
                return u
        except Exception:
            pass

    tid = _get(t, "id")
    # 2) common endpoints
    candidates: List[Tuple[str, Dict[str, Any]]] = [
        ("tickets.view", {"id": tid}),
        ("tickets.detail", {"id": tid}),
        ("tickets.ticket_view", {"id": tid}),
        ("ticket.view", {"id": tid}),
        ("tickets.show", {"ticket_id": tid}),
        ("tickets.details", {"ticket_id": tid}),
        ("tickets.panel", {}),
        ("tickets.index", {}),
    ]
    for ep, vals in candidates:
        try:
            u = url_for(ep, **vals)
            if u:
                return u
        except Exception:
            continue

    # 3) path patterns
    if tid is not None:
        return f"/tickets/{tid}"

    # 4) fallback
    return "/tickets"


def _attachments_of(t: Any) -> List[Dict[str, Any]]:
    """
    Normalize attachments: [{id, filename, url, size}]
    Supports common relation names and link builders.
    """
    items: List[Dict[str, Any]] = []
    rel_name = None
    for cand in ("attachments", "files", "documents"):
        if hasattr(t, cand):
            rel_name = cand
            break
    if not rel_name:
        return items
    rel = getattr(t, rel_name, None)
    if rel is None:
        return items

    try:
        for a in list(rel):
            aid = _get(a, "id")
            fname = _get(a, "filename", "name", "orig_name", default="attachment")
            # Try model-provided url getters first
            url = None
            for attr in ("url", "get_url", "public_url", "download_url"):
                try:
                    v = getattr(a, attr)
                    url = v() if callable(v) else v
                    if url:
                        break
                except Exception:
                    pass
            # Try app endpoints
            if not url and aid is not None:
                for ep, vals in (
                    ("tickets.download_attachment", {"attachment_id": aid}),
                    ("tickets.attachment", {"attachment_id": aid}),
                    ("tickets.download", {"id": aid}),
                ):
                    try:
                        url = url_for(ep, **vals)
                        if url:
                            break
                    except Exception:
                        continue
            # Final fallback (static-ish pattern)
            if not url and aid is not None:
                url = f"/tickets/attachments/{aid}"

            items.append({
                "id": aid,
                "filename": fname or "attachment",
                "url": url,
                "size": _get(a, "size", "filesize")
            })
    except Exception:
        # Be resilient — attachments are optional
        pass
    return items


def _departments_of(t: Any) -> List[str]:
    for cand in ("departments", "department_list", "teams", "groups"):
        if hasattr(t, cand):
            try:
                return [str(_get(d, "name", "title", default=d)) for d in list(getattr(t, cand) or []) if d is not None]
            except Exception:
                return []
    return []


def _assignees_of(t: Any) -> List[Dict[str, Any]]:
    for cand in ("assignees", "assigned_users", "users"):
        if hasattr(t, cand):
            try:
                return [{"id": _get(u, "id"), "name": _full_name(u)} for u in list(getattr(t, cand) or [])]
            except Exception:
                return []
    return []


def _comments_of(t: Any) -> List[Dict[str, Any]]:
    """
    Returns comments as:
      { id, author_name, text, created_at_iso }
    """
    rel_name = None
    for cand in ("comments", "ticket_comments", "notes", "messages"):
        if hasattr(t, cand):
            rel_name = cand
            break
    if not rel_name:
        return []

    out: List[Dict[str, Any]] = []
    try:
        for c in list(getattr(t, rel_name) or []):
            author = _get(c, "author", "user", "creator")
            out.append({
                "id": _get(c, "id"),
                "author_name": _full_name(author) if author else "—",
                "text": _get(c, "text", "body", "content", default=""),
                # IMPORTANT: return ISO string under "created_at_iso" to match JS
                "created_at_iso": (_to_dt(_get(c, "created_at", "created", "timestamp")) or datetime.utcnow()).isoformat()
            })
    except Exception:
        return []
    # Sort by created time (ISO lexicographic works)
    out.sort(key=lambda x: str(x.get("created_at_iso") or ""))
    return out


def _period_of(t: Any) -> Tuple[datetime, datetime]:
    """
    Build start/end for modal header: prefer created_at -> due_at; otherwise
    use the strongest single datetime for a 1h block.
    """
    created = _to_dt(_get(t, "created_at", "created"))
    due = _to_dt(_get(t, "due_at", "due_date", "finish_at", "planned_end_at"), end=True)
    if created and due and due >= created:
        return created, due

    for k in ("scheduled_at", "planned_at", "start_at", "due_at", "due_date"):
        v = _to_dt(_get(t, k))
        if v:
            return v, v + timedelta(hours=1)

    now = datetime.utcnow()
    return now, now + timedelta(hours=1)


# ------------------------- route -------------------------

@bp.route("/api/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def api_ticket_details(ticket_id: int):
    """
    Returns a rich ticket payload for the Ticket modal:
    {
      id, title, start_dt, end_dt, url,
      status, priority,
      description,
      assignees: [{id, name}],
      departments: [name, ...],
      comments: [{id, author_name, text, created_at_iso}],
      attachments: [{id, filename, url, size}]
    }
    """
    try:
        # If Tickets app is missing, surface clearly (501) but keep route alive.
        if Ticket is None:
            return jsonify({"error": "Tickets module not available"}), 501

        # Eager-load common rels if present
        from sqlalchemy.orm import joinedload  # local import to avoid hard dep if unused
        q = Ticket.query

        def _has(name: str) -> bool:
            return hasattr(Ticket, name)

        opts = []
        for cand in ("assignees", "assigned_users", "users"):
            if _has(cand):
                opts.append(joinedload(getattr(Ticket, cand)))
                break
        for cand in ("departments", "department_list", "teams", "groups"):
            if _has(cand):
                opts.append(joinedload(getattr(Ticket, cand)))
                break
        for cand in ("comments", "ticket_comments", "notes", "messages"):
            if _has(cand):
                opts.append(joinedload(getattr(Ticket, cand)))
                break
        for cand in ("attachments", "files", "documents"):
            if _has(cand):
                opts.append(joinedload(getattr(Ticket, cand)))
                break
        if opts:
            q = q.options(*opts)

        t = q.get(ticket_id)
        if not t:
            return jsonify({"error": "Not found"}), 404

        s_dt, e_dt = _period_of(t)

        payload = {
            "id": _get(t, "id"),
            "title": _get(t, "title", "name") or f"Ticket #{_get(t,'id')}",
            "start_dt": s_dt.isoformat() if s_dt else None,
            "end_dt": e_dt.isoformat() if e_dt else None,
            "url": _ticket_url(t),
            "status": _label(_get(t, "status")),
            "priority": _label(_get(t, "priority")),
            "description": _get(t, "description", "body", "content", default="") or "",
            "assignees": _assignees_of(t),
            "departments": _departments_of(t),
            "comments": _comments_of(t),
            "attachments": _attachments_of(t),
        }
        return jsonify({"ticket": payload})

    except Exception:
        current_app.logger.exception("api_ticket_details: unhandled error")
        return jsonify({"error": "Internal server error"}), 500
