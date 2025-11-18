# app/notifications/feed_notifications/models.py
from datetime import datetime
from sqlalchemy import JSON  # portable across SQLite/Postgres
from app.extensions import db
from app.models import User  # import your real User model

# Use the actual users table name dynamically (usually "users")
USER_TABLE = User.__tablename__


class FeedNotification(db.Model):
    __tablename__ = "feed_notifications"

    id = db.Column(db.BigInteger, primary_key=True)

    # Foreign Keys
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{USER_TABLE}.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )  # recipient

    actor_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{USER_TABLE}.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )  # who performed the action

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("feed_posts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    kind = db.Column(db.String(32), nullable=False)  # 'post_created' | 'comment_added' | 'reacted'

    # Portable JSON (works on SQLite & Postgres)
    payload = db.Column(JSON, nullable=True)  # {"title": "...", "emoji": "👍", "comment_id": 123, ...}

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)
    seen_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relationship helpers
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("feed_notifications", lazy="dynamic"),
    )

    actor = db.relationship(
        "User",
        foreign_keys=[actor_id],
        backref=db.backref("feed_actions", lazy="dynamic"),
    )

    __table_args__ = (
        db.Index("ix_feed_notifications_unseen", "user_id", "seen_at"),
    )
