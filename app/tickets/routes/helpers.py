# app/tickets/routes/helpers.py
import os
from pathlib import Path
from datetime import date
from uuid import uuid4
from typing import Optional, List, Any

from flask import current_app, request, abort
from werkzeug.utils import secure_filename

from app.models import User, Department
from app.tickets.models import TicketPriority, TicketStatus, TicketChecklist

# -------------------------
# Request / file helpers
# -------------------------
def is_spa_request() -> bool:
    hx = request.headers.get("HX-Request") == "true"
    fetch = request.headers.get("X-Requested-With") in {"XMLHttpRequest", "fetch"}
    spa_qs = request.args.get("__spa") == "1"
    return hx or fetch or spa_qs

def attachments_root() -> Path:
    root = current_app.config.get("ATTACHMENTS_DIR") or os.path.join(current_app.root_path, "attachments")
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def safe_attachment_abs_path(rel_path: str) -> Path:
    if not rel_path:
        abort(400, description="Missing path")
    rel_clean = rel_path.replace("\\", "/").lstrip("/")
    root = attachments_root()
    abs_path = (root / rel_clean).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError:
        abort(400, description="Invalid path")
    if not abs_path.exists():
        abort(404)
    return abs_path

def ticket_upload_root() -> Path:
    base = current_app.config.get("TICKETS_UPLOADS_DIR")
    if not base:
        base = os.path.join(current_app.instance_path, "ticket_uploads")
    p = Path(base).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_comment_file_under_ticket_root(file_storage, rel_dir: Path) -> Optional[str]:
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None
    root = attachments_root()  # ATTACHMENTS_DIR
    abs_dir = (root / rel_dir).resolve()
    abs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_{secure_filename(file_storage.filename)}"
    abs_path = abs_dir / filename
    file_storage.save(str(abs_path))
    return str((rel_dir / filename).as_posix())

# -------------------------
# Permission helpers
# -------------------------
def creator_id(ticket) -> Optional[int]:
    for cand in ("created_by_id", "creator_id", "user_id", "author_id", "owner_id"):
        val = getattr(ticket, cand, None)
        if isinstance(val, int):
            return val
    for rel in ("created_by", "creator", "user", "author", "owner"):
        obj = getattr(ticket, rel, None)
        if obj is not None and hasattr(obj, "id") and isinstance(obj.id, int):
            return obj.id
    return None

def is_assignee(user, ticket) -> bool:
    assignees = getattr(ticket, "assignees", None) or []
    try:
        return any(getattr(u, "id", None) == user.id for u in assignees)
    except Exception:
        return False

def shares_department(user, ticket) -> bool:
    t_depts = getattr(ticket, "departments", None) or []
    u_depts = getattr(user, "departments", None) or []
    if not t_depts or not u_depts:
        return False
    t_ids = {getattr(d, "id", None) for d in t_depts}
    u_ids = {getattr(d, "id", None) for d in u_depts}
    return bool(t_ids & u_ids)

def enforce_can_view(user, ticket):
    if user is None:
        abort(403)
    if creator_id(ticket) == user.id:
        return
    if is_assignee(user, ticket):
        return
    if shares_department(user, ticket):
        return
    abort(403)

def enforce_can_comment(user, ticket):
    """Allow comments from creator, assignees, or users in the same department; block if completed."""
    status_val = getattr(ticket, "status", None)
    try:
        is_completed = (status_val == TicketStatus.COMPLETED)
    except Exception:
        is_completed = (str(status_val).upper() == "COMPLETED")
    if is_completed:
        abort(403)
    if creator_id(ticket) == user.id or is_assignee(user, ticket) or shares_department(user, ticket):
        return
    abort(403)

def enforce_can_mark_complete(user, ticket):
    if creator_id(ticket) == user.id or is_assignee(user, ticket):
        return
    abort(403)

# -------------------------
# Labels and choice loaders
# -------------------------
def user_label(u: User) -> str:
    first = (getattr(u, "first_name", "") or "").strip()
    last  = (getattr(u, "last_name", "") or "").strip()
    if first or last:
        return f"{first} {last}".strip()
    for a in ("username", "email", "name"):
        v = getattr(u, a, None)
        if v:
            return str(v)
    return f"User #{getattr(u, 'id', '—')}"

def dept_label(d: Department) -> str:
    for a in ("name", "title"):
        v = getattr(d, a, None)
        if v:
            return str(v)
    return f"Dept #{getattr(d, 'id', '—')}"

def load_users_and_departments():
    user_order = getattr(User, "first_name", None) or getattr(User, "name", None) \
                 or getattr(User, "username", None) or getattr(User, "email", None) or User.id
    dept_order = getattr(Department, "name", None) or getattr(Department, "title", None) or Department.id
    users = User.query.order_by(user_order.asc()).all()
    departments = Department.query.order_by(dept_order.asc()).all()
    return users, departments

def parse_priority(val: str | None) -> TicketPriority:
    if not val:
        return TicketPriority.MEDIUM
    s = str(val).strip()
    mapping = {
        "urgent": TicketPriority.URGENT,
        "high": TicketPriority.HIGH,
        "medium": TicketPriority.MEDIUM,
        "low": TicketPriority.LOW,
        "URGENT": TicketPriority.URGENT,
        "HIGH": TicketPriority.HIGH,
        "MEDIUM": TicketPriority.MEDIUM,
        "LOW": TicketPriority.LOW,
        "Urgent": TicketPriority.URGENT,
        "High": TicketPriority.HIGH,
        "Medium": TicketPriority.MEDIUM,
        "Low": TicketPriority.LOW,
    }
    return mapping.get(s, mapping.get(s.upper(), TicketPriority.MEDIUM))

def today_date() -> date:
    return date.today()

# -------------------------
# Checklist parsers (JSON or classic arrays)
# -------------------------
def _first_nonempty_getlist(*names: str) -> Optional[List[str]]:
    for name in names:
        vals = request.form.getlist(name)
        if vals:
            return vals
    return None

def _first_nonempty_get(*names: str) -> Optional[str]:
    for name in names:
        v = request.form.get(name)
        if v not in (None, ""):
            return v
    return None

def _truthy(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if x is None:
        return False
    s = str(x).strip().lower()
    return s in {"1", "true", "yes", "on"}

def save_checklists_for_ticket_from_request(ticket_id: int) -> None:
    """
    Saves TicketChecklist rows for the given ticket_id from the current request.
    Supports:
      1) JSON in any of: checklists_json, checklist_json, check_json, checklists, checklist
         - grouped: [{title, items:[{text/title, done/completed}]}...]
         - flat:    [{title/text, position?, completed?}, ...]
      2) Classic arrays (parallel inputs), any of the following aliases:
         - titles:   chk_title[], checklist_title[], check_title[], titles[], checklist_items[], checklist_item[]
         - done:     chk_completed[], checklist_completed[], check_completed[], completed[]
         - position: chk_position[], checklist_position[], position[]
         - sec idx:  chk_section_index[], checklist_section_index[]
         - sec title:chk_section_title[], checklist_section_title[]
    If only titles are provided, it will create a flat checklist in given order.
    """
    from app.extensions import db  # local import to avoid circulars
    import json

    # --- Try JSON (multiple aliases) ---
    raw = _first_nonempty_get(
        "checklists_json", "checklist_json", "check_json", "checklists", "checklist"
    )
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None

        if isinstance(data, list):
            # GROUPED: list of sections with "items"
            if data and isinstance(data[0], dict) and "items" in data[0]:
                global_pos = 0
                for sidx, sec in enumerate(data):
                    sec_title = (sec.get("title") or "").strip() or None
                    items = sec.get("items") or []
                    for it in items:
                        text = (it.get("text") or it.get("title") or "").strip()
                        if not text:
                            continue
                        ch = TicketChecklist(
                            ticket_id=ticket_id,
                            section_index=int(sidx),
                            section_title=sec_title,
                            title=text,
                            position=global_pos,
                            completed=_truthy(it.get("done") or it.get("completed")),
                        )
                        db.session.add(ch)
                        global_pos += 1
                return
            # FLAT: list of items
            for idx, it in enumerate(data):
                if isinstance(it, dict):
                    text = (it.get("title") or it.get("text") or "").strip()
                    pos = it.get("position", idx)
                    try:
                        pos = int(pos)
                    except Exception:
                        pos = idx
                    completed = _truthy(it.get("completed"))
                else:
                    text = str(it).strip()
                    pos = idx
                    completed = False
                if not text:
                    continue
                db.session.add(TicketChecklist(
                    ticket_id=ticket_id,
                    section_index=0,
                    section_title=None,
                    title=text,
                    position=pos,
                    completed=completed,
                ))
            return

    # --- Classic arrays ---
    titles = _first_nonempty_getlist(
        "chk_title", "chk_title[]",
        "checklist_title", "checklist_title[]",
        "check_title", "check_title[]",
        "titles", "titles[]",
        "checklist_items", "checklist_items[]",
        "checklist_item", "checklist_item[]",
    ) or []
    titles = [ (t or "").strip() for t in titles ]
    titles = [ t for t in titles if t ]  # drop empties
    if not titles:
        return  # nothing to save

    completed_list = _first_nonempty_getlist(
        "chk_completed", "chk_completed[]",
        "checklist_completed", "checklist_completed[]",
        "check_completed", "check_completed[]",
        "completed", "completed[]",
    ) or []
    position_list  = _first_nonempty_getlist(
        "chk_position", "chk_position[]",
        "checklist_position", "checklist_position[]",
        "position", "position[]",
    ) or []
    sec_index_list = _first_nonempty_getlist(
        "chk_section_index", "chk_section_index[]",
        "checklist_section_index", "checklist_section_index[]",
    ) or []
    sec_title_list = _first_nonempty_getlist(
        "chk_section_title", "chk_section_title[]",
        "checklist_section_title", "checklist_section_title[]",
    ) or []

    # Completed flags
    if len(completed_list) == len(titles):
        completed_flags = [_truthy(v) for v in completed_list]
    else:
        idx_set = {str(v).strip() for v in completed_list}
        completed_flags = [str(i) in idx_set for i in range(len(titles))]

    # Positions
    parsed_positions: List[int] = []
    for i in range(len(titles)):
        try:
            parsed_positions.append(int(position_list[i]))
        except Exception:
            parsed_positions.append(i)

    # Section index + title
    parsed_sec_idx: List[int] = []
    for i in range(len(titles)):
        try:
            parsed_sec_idx.append(int(sec_index_list[i]))
        except Exception:
            parsed_sec_idx.append(0)

    parsed_sec_title: List[Optional[str]] = []
    for i in range(len(titles)):
        try:
            st = (sec_title_list[i] or "").strip()
            parsed_sec_title.append(st or None)
        except Exception:
            parsed_sec_title.append(None)

    # Persist rows
    for i, title in enumerate(titles):
        db.session.add(TicketChecklist(
            ticket_id=ticket_id,
            section_index=parsed_sec_idx[i],
            section_title=parsed_sec_title[i],
            title=title,
            position=parsed_positions[i],
            completed=bool(completed_flags[i]),
        ))
    # commit by caller
