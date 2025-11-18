# app/callendar/models.py
from __future__ import annotations

from datetime import datetime
import enum

from app.extensions import db
from app.models import User  # assumes your main User model uses __tablename__='users'


class RepeatType(enum.Enum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class InviteStatus(enum.Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    TENTATIVE = "TENTATIVE"


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    start_dt = db.Column(db.DateTime, nullable=False)
    end_dt = db.Column(db.DateTime, nullable=False)

    timezone = db.Column(db.String(64), nullable=True)
    repeat = db.Column(
        db.Enum(RepeatType, name="repeat_type"),
        default=RepeatType.NONE,
        nullable=False,
    )

    organiser_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    organiser = db.relationship(
        User,
        backref=db.backref("organized_events", lazy="dynamic"),
        foreign_keys=[organiser_id],
    )

    notify_on_responses = db.Column(db.Boolean, default=False, nullable=False)
    attachment_path = db.Column(db.String(512), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # IMPORTANT: use a collection-loading strategy (not dynamic) so joinedload/selectinload works
    attendees = db.relationship(
        "EventAttendee",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reminders = db.relationship(
        "EventReminder",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self, include_attendees: bool = False):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "start_dt": self.start_dt.isoformat(),
            "end_dt": self.end_dt.isoformat(),
            "timezone": self.timezone,
            "repeat": self.repeat.value if self.repeat else RepeatType.NONE.value,
            "organiser_id": self.organiser_id,
            "notify_on_responses": self.notify_on_responses,
            "attachment_path": self.attachment_path,
        }
        if include_attendees:
            data["attendees"] = [a.to_dict() for a in (self.attendees or [])]
        return data


class EventAttendee(db.Model):
    __tablename__ = "event_attendees"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status = db.Column(
        db.Enum(InviteStatus, name="invite_status"),
        default=InviteStatus.INVITED,
        nullable=False,
    )
    responded_at = db.Column(db.DateTime, nullable=True)

    # Backrefs
    event = db.relationship("Event", back_populates="attendees", lazy="joined")
    user = db.relationship(
        User, backref=db.backref("event_attendances", lazy="dynamic")
    )

    __table_args__ = (db.UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "user_id": self.user_id,
            "status": self.status.value if self.status else InviteStatus.INVITED.value,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }


class EventReminder(db.Model):
    __tablename__ = "event_reminders"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    minutes_before = db.Column(db.Integer, nullable=False, default=15)

    event = db.relationship("Event", back_populates="reminders", lazy="joined")
