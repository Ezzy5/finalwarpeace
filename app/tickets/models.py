# app/tickets/models.py
from enum import Enum
from datetime import datetime
from app.extensions import db

# -------------------------
# Enums
# -------------------------
class TicketStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"


class TicketPriority(str, Enum):
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"
    URGENT = "Urgent"


# -------------------------
# Association tables
# -------------------------
ticket_assignees = db.Table(
    "ticket_assignees",
    db.Column("ticket_id", db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

ticket_departments = db.Table(
    "ticket_departments",
    db.Column("ticket_id", db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), primary_key=True),
    db.Column("department_id", db.Integer, db.ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
)


# -------------------------
# Core models
# -------------------------
class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    creator_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    status = db.Column(
        db.Enum(TicketStatus, native_enum=False, name="ticketstatus"),
        nullable=False,
        default=TicketStatus.IN_PROGRESS,
        server_default=TicketStatus.IN_PROGRESS.value,
    )

    priority = db.Column(
        db.Enum(TicketPriority, native_enum=False, name="ticketpriority"),
        nullable=False,
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
    )

    due_date = db.Column(db.Date)

    # Parent/subticket
    parent_ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
    parent = db.relationship("Ticket", remote_side=[id], backref=db.backref("subtickets", lazy="selectin"))

    # Relationships
    creator = db.relationship("User", backref="created_tickets", lazy="joined")

    assignees = db.relationship(
        "User",
        secondary=ticket_assignees,
        lazy="selectin",
    )

    departments = db.relationship(
        "Department",
        secondary=ticket_departments,
        lazy="selectin",
    )

    comments = db.relationship(
        "TicketComment",
        backref="ticket",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketComment.created_at.asc()",
    )

    # Checklists (kept ordered by position; sections are separated by section_index)
    checklists = db.relationship(
        "TicketChecklist",
        backref="ticket",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketChecklist.position.asc()",
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} title={self.title!r} status={self.status}>"


class TicketComment(db.Model):
    __tablename__ = "ticket_comments"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id   = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    body = db.Column(db.Text)
    attachment_path = db.Column(db.String(500))

    # Store the status we changed TO (optional)
    status_change_to = db.Column(
        db.Enum(TicketStatus, native_enum=False, name="ticketstatus"),
        nullable=True,
    )

    # Author
    user = db.relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<TicketComment id={self.id} ticket_id={self.ticket_id}>"


class TicketChecklist(db.Model):
    __tablename__ = "ticket_checklists"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)

    # Sectioning
    section_index = db.Column(db.Integer, nullable=False, default=0, index=True)
    section_title = db.Column(db.String(255))  # optional: kept from the UI section header

    # The text of the checklist item
    title = db.Column(db.String(255), nullable=False)

    # Order within the ticket (global order or within section; we keep simple global)
    position = db.Column(db.Integer, nullable=False, default=0, index=True)

    # Whether this item is completed
    completed = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TicketChecklist id={self.id} ticket_id={self.ticket_id} sec={self.section_index} pos={self.position} completed={self.completed}>"
