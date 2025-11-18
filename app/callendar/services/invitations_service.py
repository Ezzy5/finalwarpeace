from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from flask import current_app
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import User
from ..models import Event, EventAttendee, InviteStatus


def list_invitations_for_user(user_id: int) -> List[EventAttendee]:
    """All pending invitations for the user."""
    return (
        EventAttendee.query.options(
            joinedload(EventAttendee.event).joinedload(Event.attendees),
            joinedload(EventAttendee.event).joinedload(Event.reminders),
        )
        .filter(EventAttendee.user_id == user_id, EventAttendee.status == InviteStatus.INVITED)
        .order_by(EventAttendee.id.desc())
        .all()
    )


def get_invitation_map_for_events(event_ids: Iterable[int], user_id: int) -> Dict[int, InviteStatus]:
    """Return a map {event_id: status} for quick lookup in views."""
    rows = (
        EventAttendee.query.filter(
            EventAttendee.user_id == user_id,
            EventAttendee.event_id.in_(list(event_ids) or [0]),
        ).all()
    )
    return {r.event_id: r.status for r in rows}


def respond_to_invitation(event_id: int, user_id: int, status: InviteStatus) -> EventAttendee:
    """User responds to an invitation. If event.notify_on_responses -> notify organiser (hook)."""
    ea = EventAttendee.query.filter_by(event_id=event_id, user_id=user_id).first()
    if not ea:
        # User can still be attached on-the-fly if invited externally
        ea = EventAttendee(event_id=event_id, user_id=user_id)
        db.session.add(ea)
        db.session.flush()

    ea.status = status
    ea.responded_at = datetime.utcnow()
    db.session.commit()

    # Notify organiser if needed
    _maybe_notify_on_response(ea)

    return ea


# -----------------------------
# Notification (hook / placeholder)
# -----------------------------
def _maybe_notify_on_response(ea: EventAttendee) -> None:
    try:
        event = (
            Event.query.options(joinedload(Event.organiser))
            .filter_by(id=ea.event_id)
            .first()
        )
        if not event or not event.notify_on_responses:
            return

        organiser: Optional[User] = getattr(event, "organiser", None)
        invitee: Optional[User] = ea.user

        # Hook point: integrate with your notifications system
        # You might send an email, in-app notification, Slack, etc.
        # For now we just log to the Flask logger to prove the flow works.
        current_app.logger.info(
            "[Callendar] Invitation response: user=%s (%s) -> event=%s (%s) status=%s",
            getattr(invitee, "username", invitee.id if invitee else "unknown"),
            getattr(invitee, "email", ""),
            event.id,
            event.title,
            ea.status.value,
        )

    except Exception as exc:
        current_app.logger.exception("Failed to notify organiser on response: %s", exc)
