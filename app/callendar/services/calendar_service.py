# app/callendar/services/calendar_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Tuple, Any

from app.extensions import db
from ..models import Event, RepeatType

try:
    from ..models import EventAttendee  # optional join model
except Exception:
    EventAttendee = None  # type: ignore

try:
    from ..models import EventReminder  # optional reminders model
except Exception:
    EventReminder = None  # type: ignore


# ---------- utils ----------
def _ensure_timezone_str(tz: Optional[str]) -> Optional[str]:
    tz = (tz or "").strip()
    return tz or None


def _coerce_repeat(rt: Optional[RepeatType | str]) -> RepeatType:
    if isinstance(rt, RepeatType):
        return rt
    if not rt:
        return RepeatType.NONE
    key = str(rt).upper().strip()
    return RepeatType[key] if key in RepeatType.__members__ else RepeatType.NONE


def _safe_ints(values) -> List[int]:
    out: List[int] = []
    for v in values or []:
        try:
            out.append(int(v))
        except Exception:
            continue
    return out


def _parse_minutes_any(value: Any) -> List[int]:
    """
    Accepts:
      - list/tuple/set of ints/strings (e.g., [5, "15"])
      - single int (5)
      - CSV string ("5,10" or "[5, 10]")
      - None
    Returns unique positive ints, DESC sorted (e.g., [15, 5]).
    """
    if value is None:
        return []
    src: List[Any]
    if isinstance(value, (list, tuple, set)):
        src = list(value)
    elif isinstance(value, str):
        s = value.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        src = [p.strip() for p in s.split(",") if p.strip()]
    else:
        src = [value]

    mins: List[int] = []
    for x in src:
        try:
            n = int(x)
            if n > 0:
                mins.append(n)
        except Exception:
            continue
    # unique + sorted DESC
    return sorted(set(mins), reverse=True)


# ---------- reminders: model-agnostic handling ----------
_MINUTE_CANDIDATES = (
    "minutes",
    "minutes_before",
    "offset_minutes",
    "delta_minutes",
    "remind_at_minutes",
)

_EVENT_FK_CANDIDATES = (
    "event_id",
    "calendar_event_id",
    # if neither exists, we’ll fallback to relationship field "event"
)


def _detect_minutes_attr() -> Optional[str]:
    """Return the column name to store minutes in EventReminder, or None if not present."""
    if EventReminder is None:
        return None
    for name in _MINUTE_CANDIDATES:
        if hasattr(EventReminder, name):
            return name
    return None


def _detect_event_fk() -> Optional[str]:
    """Return the FK column name if exists; otherwise None (we'll use relationship 'event')."""
    if EventReminder is None:
        return None
    for name in _EVENT_FK_CANDIDATES:
        if hasattr(EventReminder, name):
            return name
    return None


def _get_existing_reminder_minutes(reminder_obj) -> Optional[int]:
    """Read the minutes value from a reminder row regardless of the actual column name."""
    for name in _MINUTE_CANDIDATES:
        if hasattr(reminder_obj, name):
            try:
                return int(getattr(reminder_obj, name))
            except Exception:
                try:
                    return int(float(getattr(reminder_obj, name)))
                except Exception:
                    return None
    return None


def upsert_reminders(event: Event, reminder_minutes_list=None) -> None:
    """
    Create/remove EventReminder rows to match the list of minutes.
    Works with different schema variants:
    - minutes / minutes_before / offset_minutes / delta_minutes / remind_at_minutes
    - event_id / calendar_event_id OR relationship 'event'
    """
    if EventReminder is None:
        return

    minute_attr = _detect_minutes_attr()
    if not minute_attr:
        # No compatible minutes column found — nothing to do.
        return

    target_minutes = sorted({int(m) for m in _safe_ints(reminder_minutes_list or []) if int(m) > 0})

    # current reminders (relationship may be named "reminders"; fallback safe)
    existing_list = list(getattr(event, "reminders", []) or [])
    existing_by_min = {}
    for r in existing_list:
        m = _get_existing_reminder_minutes(r)
        if m is not None:
            existing_by_min[m] = r

    # remove obsolete
    for r in existing_list:
        m = _get_existing_reminder_minutes(r)
        if m is None or m not in target_minutes:
            db.session.delete(r)

    # add new
    fk_attr = _detect_event_fk()  # e.g., event_id or calendar_event_id
    for m in target_minutes:
        if m in existing_by_min:
            continue
        # Build ctor kwargs dynamically
        kwargs = {minute_attr: m}
        if fk_attr:
            kwargs[fk_attr] = event.id
            inst = EventReminder(**kwargs)
        else:
            # use relationship "event" if available
            if hasattr(EventReminder, "event"):
                kwargs["event"] = event
                inst = EventReminder(**kwargs)
            else:
                # As a last resort, try with event_id if exists; otherwise skip
                if hasattr(EventReminder, "event_id"):
                    kwargs["event_id"] = event.id
                    inst = EventReminder(**kwargs)
                else:
                    # no way to connect — skip gracefully
                    continue
        db.session.add(inst)


def _apply_event_reminders_on_event(ev: Event, mins: List[int]) -> None:
    """
    Persist reminder minutes onto the Event model if such columns exist, so
    reminder scanning that reads from Event.* sees them.
    Preference: reminder_minutes_list (full list). If missing, fallback to reminder_minutes_before (single).
    """
    if hasattr(ev, "reminder_minutes_list"):
        # store the whole list; if your column is JSON, SQLAlchemy will handle
        setattr(ev, "reminder_minutes_list", mins)
    elif hasattr(ev, "reminder_minutes_before"):
        setattr(ev, "reminder_minutes_before", (mins[0] if mins else None))
    # else: no event-level reminder fields — scanning will rely on EventReminder rows only


# ---------- attendees (supports join model or M2M) ----------
def set_attendees(event: Event, user_ids) -> None:
    """
    Update attendees to match user_ids.
    Works if you have:
      - EventAttendee join model with columns (event_id, user_id), or
      - direct many-to-many relationship `event.users`
    """
    user_ids_set = set(_safe_ints(user_ids or []))

    if EventAttendee is not None:
        current = list(getattr(event, "attendees", []) or [])
        current_ids = {getattr(a, "user_id", None) for a in current}
        for a in current:
            if getattr(a, "user_id", None) not in user_ids_set:
                db.session.delete(a)
        for uid in user_ids_set:
            if uid not in current_ids:
                db.session.add(EventAttendee(event_id=event.id, user_id=uid))
        return

    # fallback: direct relationship `users`
    rel = getattr(event, "users", None)
    if rel is None:
        return
    try:
        from app.models import User
        wanted = {
            u.id: u
            for u in db.session.query(User).filter(User.id.in_(list(user_ids_set))).all()
        }
    except Exception:
        wanted = {}

    current_users = list(rel)
    current_ids = {getattr(u, "id", None) for u in current_users}
    for u in current_users:
        if getattr(u, "id", None) not in user_ids_set:
            try:
                rel.remove(u)
            except Exception:
                pass
    for uid in user_ids_set:
        if uid not in current_ids and uid in wanted:
            try:
                rel.append(wanted[uid])
            except Exception:
                pass


# ---------- CRUD ----------
def create_event(
    *,
    title: str,
    start_dt: datetime,
    end_dt: datetime,
    organiser_id: int,
    description: Optional[str] = None,
    timezone: Optional[str] = None,
    repeat: Optional[RepeatType | str] = None,
    notify_on_responses: bool = False,
    attendees_user_ids=None,
    reminder_minutes_list=None,           # may be list/CSV/single
    reminder_minutes_before: Optional[int] = None,  # optional single
    attachment_file=None,
) -> Event:
    ev = Event(
        title=title.strip(),
        start_dt=start_dt,
        end_dt=end_dt,
        organiser_id=organiser_id,
        description=(description or None),
        timezone=_ensure_timezone_str(timezone),
        repeat=_coerce_repeat(repeat),
        notify_on_responses=bool(notify_on_responses),
    )
    db.session.add(ev)
    db.session.flush()  # have ev.id

    if attachment_file:
        try:
            ev.save_attachment(attachment_file)  # optional helper on your model
        except Exception:
            pass

    if attendees_user_ids:
        set_attendees(ev, attendees_user_ids)

    # ---- REMINDERS: normalize + persist on Event and EventReminder
    mins = _parse_minutes_any(reminder_minutes_list if reminder_minutes_list is not None else reminder_minutes_before)
    _apply_event_reminders_on_event(ev, mins)  # so scanning that reads Event.* sees them
    upsert_reminders(ev, mins)                 # keep EventReminder rows in sync if that model exists

    db.session.commit()
    return ev


def update_event(
    event_id: int,
    * ,
    title: Optional[str] = None,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
    organiser_id: Optional[int] = None,
    description: Optional[str] = None,
    timezone: Optional[str] = None,
    repeat: Optional[RepeatType | str] = None,
    notify_on_responses: Optional[bool] = None,
    attendees_user_ids=None,
    reminder_minutes_list=None,               # may be list/CSV/single
    reminder_minutes_before: Optional[int] = None,
    attachment_file=None,
) -> Event:
    ev = db.session.get(Event, int(event_id))
    if not ev:
        raise ValueError("Event not found")

    if title is not None:
        ev.title = title.strip()
    if start_dt is not None:
        ev.start_dt = start_dt
    if end_dt is not None:
        ev.end_dt = end_dt
    if organiser_id is not None:
        ev.organiser_id = organiser_id
    if description is not None:
        ev.description = description or None
    if timezone is not None:
        ev.timezone = _ensure_timezone_str(timezone)
    if repeat is not None:
        ev.repeat = _coerce_repeat(repeat)
    if notify_on_responses is not None:
        ev.notify_on_responses = bool(notify_on_responses)

    if attachment_file:
        try:
            ev.save_attachment(attachment_file)
        except Exception:
            pass

    if attendees_user_ids is not None:
        set_attendees(ev, attendees_user_ids)

    # ---- REMINDERS: only update if caller provided something
    if (reminder_minutes_list is not None) or (reminder_minutes_before is not None):
        mins = _parse_minutes_any(reminder_minutes_list if reminder_minutes_list is not None else reminder_minutes_before)
        _apply_event_reminders_on_event(ev, mins)
        upsert_reminders(ev, mins)

    db.session.commit()
    return ev


def delete_event(event_id: int) -> None:
    ev = db.session.get(Event, int(event_id))
    if not ev:
        return
    db.session.delete(ev)
    db.session.commit()


def get_event(event_id: int) -> Optional[Event]:
    return db.session.get(Event, int(event_id))


# ---------- querying ----------
def get_events_for_user(
    * ,
    user_id: int,
    start: Optional[datetime],
    end: Optional[datetime],
    q: Optional[str] = None,
    role_filters: Optional[dict] = None,
) -> List[Event]:
    qry = Event.query
    if start is not None:
        qry = qry.filter(Event.end_dt >= start)
    if end is not None:
        qry = qry.filter(Event.start_dt <= end)
    if q:
        like = f"%{q}%"
        qry = qry.filter(db.or_(Event.title.ilike(like), Event.description.ilike(like)))

    rf = role_filters or {}
    show_inv = rf.get("show_invitations", False)
    i_org = rf.get("i_am_organiser", False)
    i_part = rf.get("i_am_participant", False)
    i_decl = rf.get("i_declined", False)

    if not any([show_inv, i_org, i_part, i_decl]):
        qry = qry.filter(
            db.or_(
                Event.organiser_id == user_id,
                _user_is_attendee_condition(user_id),
            )
        )
    else:
        parts = []
        if i_org:
            parts.append(Event.organiser_id == user_id)
        if i_part or show_inv or i_decl:
            parts.append(_user_is_attendee_condition(user_id))
        if parts:
            qry = qry.filter(db.or_(*parts))

    qry = qry.order_by(Event.start_dt.asc()).limit(2000)
    return qry.all()


def _user_is_attendee_condition(user_id: int):
    if EventAttendee is not None:
        subq = db.session.query(EventAttendee.id).filter(
            EventAttendee.event_id == Event.id,
            EventAttendee.user_id == user_id,
        ).exists()
        return subq
    # If there is no join model, either your UI won’t show attendee-specific stuff
    # or you rely on Event.organiser_id alone.
    return db.sql.true()


# ---------- expansion ----------
@dataclass
class _Win:
    start: datetime
    end: datetime


def _overlap(a: _Win, b: _Win) -> bool:
    return not (a.end < b.start or a.start > b.end)


def expand_event_instances(
    event: Event,
    * ,
    window_start: datetime,
    window_end: datetime,
) -> List[tuple[datetime, datetime, int]]:
    rt = _coerce_repeat(getattr(event, "repeat", RepeatType.NONE))
    s = event.start_dt
    e = event.end_dt

    win = _Win(window_start, window_end)
    out: List[tuple[datetime, datetime, int]] = []

    if rt == RepeatType.NONE:
        if _overlap(_Win(s, e), win):
            out.append((max(s, win.start), min(e, win.end), event.id))
        return out

    if e <= s:
        e = s + timedelta(minutes=1)

    cur_s, cur_e = s, e

    def step_once(start: datetime, end: datetime):
        if rt == RepeatType.DAILY:
            d = timedelta(days=1)
        elif rt == RepeatType.WEEKLY:
            d = timedelta(weeks=1)
        elif rt == RepeatType.MONTHLY:
            d = timedelta(days=30)  # naive month
        elif rt == RepeatType.YEARLY:
            d = timedelta(days=365)  # naive year
        else:
            d = timedelta(days=99999)
        return start + d, end + d

    MAX_ITER = 2000
    iter_count = 0
    while cur_e < win.start and iter_count < MAX_ITER:
        cur_s, cur_e = step_once(cur_s, cur_e)
        iter_count += 1

    while cur_s <= win.end and iter_count < MAX_ITER:
        if _overlap(_Win(cur_s, cur_e), win):
            out.append((max(cur_s, win.start), min(cur_e, win.end), event.id))
        cur_s, cur_e = step_once(cur_s, cur_e)
        iter_count += 1

    return out


# ---------- Backwards-compat alias ----------
def attach_users(event: Event, user_ids) -> None:
    """
    Backwards-compatibility shim for legacy imports.
    Old code calls calendar_service.attach_users(event, user_ids).
    """
    set_attendees(event, user_ids)
