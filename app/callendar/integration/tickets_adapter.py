# app/callendar/integration/tickets_adapter.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import inspect
import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.orm.properties import RelationshipProperty
from sqlalchemy.orm import class_mapper

from app.extensions import db

# --- Soft imports; keep adapter resilient if tickets app changes slightly ---
try:
    from app.tickets.models import Ticket
except Exception:
    Ticket = None  # type: ignore

try:
    from app.tickets.permissions import visibility_filter
except Exception:
    visibility_filter = None  # type: ignore


# ------------------------ helpers ------------------------

def _is_relationship(model_cls: Any, attr_name: str) -> bool:
    if model_cls is None:
        return False
    try:
        mapper = class_mapper(model_cls)
    except UnmappedClassError:
        return False
    prop = mapper.attrs.get(attr_name)
    return isinstance(prop, RelationshipProperty)


def _first_column(model: Any, names: List[str]):
    """Return first existing SQLAlchemy column attribute by name or None."""
    if model is None:
        return None
    for n in names:
        if hasattr(model, n):
            try:
                return getattr(model, n)
            except Exception:
                continue
    return None


def _col_is_date(col) -> bool:
    """Heuristically detect Date (not DateTime) columns."""
    try:
        py = getattr(col.type, "python_type", None)
        return py is date
    except Exception:
        return False


def _to_datetime(v: Any, *, end: bool = False) -> Optional[datetime]:
    """Cast value to datetime; dates become start-of-day or end-of-day."""
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


# Relationship hints
_HAS_ASSIGNEES_REL = False
_STATUS_IS_REL = False
_PRIORITY_IS_REL = False
_HAS_DEPTS_REL = False
_ATTACH_REL_NAME = None

if Ticket is not None:
    for field in ("assignees", "assigned_users", "users"):
        if hasattr(Ticket, field) and _is_relationship(Ticket, field):
            _HAS_ASSIGNEES_REL = True
            _ASSIGNEES_FIELD = field
            break
    else:
        _ASSIGNEES_FIELD = None  # type: ignore

    _STATUS_IS_REL   = hasattr(Ticket, "status")   and _is_relationship(Ticket, "status")
    _PRIORITY_IS_REL = hasattr(Ticket, "priority") and _is_relationship(Ticket, "priority")

    # departments relationship (optional)
    for field in ("departments", "teams", "groups"):
        if hasattr(Ticket, field) and _is_relationship(Ticket, field):
            _HAS_DEPTS_REL = True
            _DEPTS_FIELD = field
            break
    else:
        _DEPTS_FIELD = None  # type: ignore

    # attachments relationship (optional)
    for field in ("attachments", "files", "documents"):
        if hasattr(Ticket, field) and _is_relationship(Ticket, field):
            _ATTACH_REL_NAME = field
            _ATTACH_REL = getattr(Ticket, field)
            break
    else:
        _ATTACH_REL = None  # type: ignore


def _guess_ticket_times(t: Any) -> Tuple[datetime, datetime]:
    created_raw = getattr(t, "created_at", None) or getattr(t, "created", None)
    due_raw = getattr(t, "due_at", None) or getattr(t, "due_date", None)

    created = _to_datetime(created_raw, end=False)
    due = _to_datetime(due_raw, end=True)

    if created and due and due >= created:
        return created, due

    for field in ("scheduled_at", "planned_at", "start_at", "due_at", "due_date"):
        if hasattr(t, field) and getattr(t, field):
            start = _to_datetime(getattr(t, field), end=False) or datetime.utcnow()
            return start, start + timedelta(hours=1)

    if created:
        return created, created + timedelta(hours=1)

    now = datetime.utcnow()
    return now, now + timedelta(hours=1)


def _ticket_title(t: Any) -> str:
    tid = getattr(t, "id", "N/A")
    title = getattr(t, "title", None) or getattr(t, "name", None) or "Ticket"
    return f"Ticket #{tid} — {title}"


def _safe_url_for(endpoint: str, **values) -> Optional[str]:
    try:
        from flask import url_for
        return url_for(endpoint, **values)
    except Exception:
        return None


def _ticket_url(t: Any) -> str:
    """
    Build a robust absolute/relative URL to view a ticket, tolerant to different apps:
    - Ticket.get_absolute_url()
    - url_for on a list of common endpoints
    - fall back to common path patterns
    """
    # 1) model method
    if hasattr(t, "get_absolute_url"):
        try:
            u = t.get_absolute_url()
            if u:
                return u
        except Exception:
            pass

    tid = getattr(t, "id", None)

    # 2) common endpoints (adjust/add if your app uses different names)
    endpoint_candidates = [
        ("tickets.view", dict(id=tid)),
        ("tickets.detail", dict(id=tid)),
        ("tickets.ticket_view", dict(id=tid)),
        ("ticket.view", dict(id=tid)),
        ("tickets.show", dict(ticket_id=tid)),
        ("tickets.details", dict(ticket_id=tid)),
        ("tickets.panel", {}),
        ("tickets.index", {}),
    ]
    for ep, vals in endpoint_candidates:
        u = _safe_url_for(ep, **vals)
        if u:
            return u

    # 3) common path patterns
    if tid is not None:
        for path in (f"/tickets/{tid}", f"/ticket/{tid}", f"/tickets/view/{tid}"):
            return path

    # 4) fallback to index/panel
    return "/tickets"


def _ticket_meta(t: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    # status
    if hasattr(t, "status"):
        s = getattr(t, "status")
        meta["status"] = getattr(s, "name", s)
    # priority
    if hasattr(t, "priority"):
        p = getattr(t, "priority")
        meta["priority"] = getattr(p, "name", p)
    # departments (optional)
    if _HAS_DEPTS_REL and _DEPTS_FIELD:
        rel = getattr(t, _DEPTS_FIELD, None)
        if rel is not None:
            try:
                meta["departments"] = [getattr(d, "name", str(d)) for d in list(rel)]
            except Exception:
                pass
    # assignees
    if _HAS_ASSIGNEES_REL and _ASSIGNEES_FIELD:
        rel = getattr(t, _ASSIGNEES_FIELD, None)
        if rel is not None:
            try:
                users = list(rel)
                meta["assignees"] = [
                    {
                        "id": getattr(u, "id", None),
                        "name": (getattr(u, "full_name", None) or getattr(u, "first_name", None) and getattr(u, "last_name", None) and f"{getattr(u,'first_name')} {getattr(u,'last_name')}")
                                or getattr(u, "username", None) or getattr(u, "email", None),
                        "email": getattr(u, "email", None),
                    }
                    for u in users
                ]
            except Exception:
                pass
    return meta


def _resolve_visibility(qry, current_user_id: int):
    if visibility_filter is None:
        return qry

    user_obj = None
    try:
        from flask_login import current_user
        if getattr(current_user, "is_authenticated", False):
            user_obj = current_user
    except Exception:
        user_obj = None

    if user_obj is None:
        try:
            from app.models import User
            user_obj = db.session.get(User, int(current_user_id))
        except Exception:
            user_obj = None

    try:
        sig = inspect.signature(visibility_filter)
        params = list(sig.parameters.values())
        if len(params) >= 2:
            return visibility_filter(qry, user_obj)
        if len(params) == 1:
            cond = visibility_filter(user_obj)
            return qry.filter(cond) if cond is not None else qry
        cond = visibility_filter(user_obj)
        try:
            return qry.filter(cond) if cond is not None else qry
        except Exception:
            return qry
    except Exception:
        return qry


def _window_overlap_condition(*, start_col, end_col, window_start: Optional[datetime], window_end: Optional[datetime]):
    TRUE = sa.sql.true()
    if start_col is None and end_col is None:
        return TRUE

    ws = window_start
    we = window_end

    if start_col is not None and _col_is_date(start_col) and ws is not None:
        ws = ws.date()
    if start_col is not None and _col_is_date(start_col) and we is not None:
        we = we.date()
    if end_col is not None and _col_is_date(end_col) and ws is not None:
        ws = ws.date()

    parts = []
    if end_col is not None:
        if we is not None and start_col is not None:
            parts.append(start_col <= we)
        if ws is not None:
            parts.append(sa.or_(end_col.is_(None), end_col >= ws))
        return sa.and_(*parts) if parts else TRUE

    if start_col is None:
        return TRUE

    if ws is not None and we is not None:
        return sa.and_(start_col >= ws, start_col <= we)
    elif ws is not None:
        return start_col >= ws
    elif we is not None:
        return start_col <= we
    return TRUE


# ------------------------ public: list blocks for calendar ------------------------

def fetch_ticket_blocks_for_calendar(
    *,
    current_user_id: int,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    search_q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if Ticket is None:
        return []

    qry = Ticket.query
    qry = _resolve_visibility(qry, current_user_id)

    opts = []
    if _HAS_ASSIGNEES_REL and _ASSIGNEES_FIELD:
        opts.append(joinedload(getattr(Ticket, _ASSIGNEES_FIELD)))
    if _STATUS_IS_REL:
        opts.append(joinedload(getattr(Ticket, "status")))
    if _PRIORITY_IS_REL:
        opts.append(joinedload(getattr(Ticket, "priority")))
    if _HAS_DEPTS_REL and _DEPTS_FIELD:
        opts.append(joinedload(getattr(Ticket, _DEPTS_FIELD)))
    if _ATTACH_REL_NAME:
        opts.append(joinedload(getattr(Ticket, _ATTACH_REL_NAME)))
    if opts:
        qry = qry.options(*opts)

    start_col = _first_column(Ticket, ["created_at", "created", "scheduled_at", "planned_at", "start_at"])
    end_col   = _first_column(Ticket, ["due_at", "due_date", "ends_at", "finish_at", "planned_end_at"])

    cond = _window_overlap_condition(
        start_col=start_col,
        end_col=end_col,
        window_start=window_start,
        window_end=window_end,
    )
    if cond is not None:
        qry = qry.filter(cond)

    if search_q:
        like = f"%{search_q.strip()}%"
        try:
            clauses = []
            if hasattr(Ticket, "title"):
                clauses.append(getattr(Ticket, "title").ilike(like))
            if hasattr(Ticket, "description"):
                clauses.append(getattr(Ticket, "description").ilike(like))
            if clauses:
                qry = qry.filter(sa.or_(*clauses))
        except Exception:
            pass

    rows = qry.limit(1000).all()

    blocks: List[Dict[str, Any]] = []
    for t in rows:
        start, end = _guess_ticket_times(t)
        meta = _ticket_meta(t)
        blocks.append(
            {
                "type": "ticket",
                "id": getattr(t, "id", None),
                "title": _ticket_title(t),
                "start_dt": start.isoformat(),
                "end_dt": end.isoformat(),
                "url": _ticket_url(t),
                "meta": meta,
            }
        )
    return blocks


# ------------------------ public: single ticket details for modal ------------------------

def fetch_single_ticket_payload(ticket_id: int, *, current_user_id: int) -> Optional[Dict[str, Any]]:
    if Ticket is None:
        return None
    qry = Ticket.query
    qry = _resolve_visibility(qry, current_user_id)

    opts = []
    if _HAS_ASSIGNEES_REL and _ASSIGNEES_FIELD:
        opts.append(joinedload(getattr(Ticket, _ASSIGNEES_FIELD)))
    if _STATUS_IS_REL:
        opts.append(joinedload(getattr(Ticket, "status")))
    if _PRIORITY_IS_REL:
        opts.append(joinedload(getattr(Ticket, "priority")))
    if _HAS_DEPTS_REL and _DEPTS_FIELD:
        opts.append(joinedload(getattr(Ticket, _DEPTS_FIELD)))
    if _ATTACH_REL_NAME:
        opts.append(joinedload(getattr(Ticket, _ATTACH_REL_NAME)))
    if opts:
        qry = qry.options(*opts)

    t = qry.get(ticket_id)
    if not t:
        return None

    start, end = _guess_ticket_times(t)
    meta = _ticket_meta(t)

    # attachments: try to normalize
    attachments: List[Dict[str, Any]] = []
    rel = getattr(t, _ATTACH_REL_NAME, None) if _ATTACH_REL_NAME else None
    if rel is not None:
        try:
            for a in list(rel):
                url = None
                name = getattr(a, "filename", None) or getattr(a, "name", None)
                # try common url getters
                for attr in ("url", "get_url", "public_url", "download_url"):
                    try:
                        v = getattr(a, attr)
                        url = v() if callable(v) else v
                        if url:
                            break
                    except Exception:
                        pass
                attachments.append({"filename": name or "attachment", "url": url})
        except Exception:
            pass

    payload = {
        "id": getattr(t, "id", None),
        "title": getattr(t, "title", None) or getattr(t, "name", None) or "Ticket",
        "description": getattr(t, "description", None) or "",
        "start_dt": start.isoformat(),
        "end_dt": end.isoformat(),
        "status": meta.get("status"),
        "priority": meta.get("priority"),
        "departments": meta.get("departments") or [],
        "assignees": meta.get("assignees") or [],
        "attachments": attachments,
        "url": _ticket_url(t),
    }
    return payload
