# app/war/models_war.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import UniqueConstraint

from app.extensions import db
from app.models import Department, User


# -----------------------------
# Link table: company <-> departments (M2M)
# -----------------------------
war_company_departments = db.Table(
    "war_company_departments",
    db.metadata,
    db.Column(
        "company_id",
        db.Integer,
        db.ForeignKey("war_companies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "department_id",
        db.Integer,
        db.ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint("company_id", "department_id", name="uq_war_company_department"),
)


class InteractionKind(str, Enum):
    meeting = "meeting"
    email = "email"
    phone = "phone"


class WarCompany(db.Model):
    __tablename__ = "war_companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    external_id = db.Column(db.String(255), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Departments that can access this company
    departments = db.relationship(
        "Department",
        secondary=war_company_departments,
        lazy="joined",  # eager-load the list of departments
    )

    # NOTE: keep symmetric with WarInteraction.company (back_populates)
    interactions = db.relationship(
        "WarInteraction",
        back_populates="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WarCompany id={self.id} name={self.name!r}>"


class WarInteraction(db.Model):
    __tablename__ = "war_interactions"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("war_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kind = db.Column(SAEnum(InteractionKind), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    archived = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Symmetric relationships
    company = db.relationship("WarCompany", back_populates="interactions", lazy="joined")
    user = db.relationship("User", lazy="joined")
    department = db.relationship("Department", lazy="joined")

    # Keep dynamic for ordering/pagination; do not eager-load here
    comments = db.relationship(
        "WarComment",
        back_populates="interaction",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WarInteraction id={self.id} company={self.company_id} user={self.user_id}>"


class WarComment(db.Model):
    __tablename__ = "war_comments"

    id = db.Column(db.Integer, primary_key=True)

    interaction_id = db.Column(
        db.Integer,
        db.ForeignKey("war_interactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    interaction = db.relationship("WarInteraction", back_populates="comments")
    user = db.relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<WarComment id={self.id} interaction={self.interaction_id} user={self.user_id}>"
