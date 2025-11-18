# app/plan/models_plan.py
from datetime import datetime, date
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Boolean, Enum as SAEnum, func
from sqlalchemy.orm import relationship, backref
from ..extensions import db

# Reuse your existing User, Department, Attachment models from your app
from ..models import User, Department, Attachment


class TaskStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    COMPLETED = "completed"
    DENIED = "denied"
    RETURNED = "returned"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanTask(db.Model):
    __tablename__ = "plan_tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # assignee
    director_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)   # creator/reviewer
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)

    start_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.ASSIGNED)
    priority = Column(SAEnum(TaskPriority), nullable=True)

    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", foreign_keys=[owner_user_id], backref=backref("plan_tasks_owned", lazy="dynamic"))
    director = relationship("User", foreign_keys=[director_id], backref=backref("plan_tasks_directed", lazy="dynamic"))
    department = relationship("Department", backref=backref("plan_tasks", lazy="dynamic"))

    comments = relationship("PlanComment", back_populates="task", cascade="all, delete-orphan", lazy="dynamic")
    activities = relationship("PlanActivity", back_populates="task", cascade="all, delete-orphan", lazy="dynamic")
    attachments = relationship("Attachment", secondary="plan_task_attachments", lazy="dynamic")

    def soft_delete(self, actor_id: int):
        if self.deleted_at:
            return
        self.deleted_at = datetime.utcnow()
        self.activities.append(PlanActivity.make(self.id, actor_id, "delete", {"deleted_at": True}))

    def restore(self, actor_id: int):
        if not self.deleted_at:
            return
        self.deleted_at = None
        self.activities.append(PlanActivity.make(self.id, actor_id, "restore", {"deleted_at": False}))


class PlanTaskAttachment(db.Model):
    __tablename__ = "plan_task_attachments"
    task_id = Column(Integer, ForeignKey("plan_tasks.id"), primary_key=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id"), primary_key=True)


class PlanComment(db.Model):
    __tablename__ = "plan_comments"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("plan_tasks.id"), index=True, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    text = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("PlanTask", back_populates="comments")
    author = relationship("User")

    # Optional: link comment to attachments via generic Attachment model
    attachments = relationship("Attachment", secondary="plan_comment_attachments", lazy="dynamic")


class PlanCommentAttachment(db.Model):
    __tablename__ = "plan_comment_attachments"
    comment_id = Column(Integer, ForeignKey("plan_comments.id"), primary_key=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id"), primary_key=True)


class PlanActivity(db.Model):
    __tablename__ = "plan_activities"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("plan_tasks.id"), index=True, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    action = Column(String(64), nullable=False)  # create, assign, reschedule, start, submit, approve, deny, delete, restore, etc.
    payload = Column(Text)                       # JSON string (old->new, notes, etc.)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("PlanTask", back_populates="activities")
    actor = relationship("User")

    @staticmethod
    def make(task_id: int, actor_id: int, action: str, payload_dict=None):
        import json
        return PlanActivity(
            task_id=task_id,
            actor_id=actor_id,
            action=action,
            payload=(json.dumps(payload_dict or {})),
        )


