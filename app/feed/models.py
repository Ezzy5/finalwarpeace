from datetime import datetime, timezone
from sqlalchemy import JSON
from app.extensions import db
from app.models import User

# always target the actual user table name
USER_TBL = User.__tablename__  # usually "users"


# --- Association / whitelist table must exist before FeedPost references it ---
class FeedPostAllowedUser(db.Model):
    __tablename__ = "feed_post_allowed_users"

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("feed_posts.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{USER_TBL}.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    added_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # relationships
    post = db.relationship(
        "FeedPost",
        back_populates="allowed_users",
        foreign_keys=[post_id],
    )
    user = db.relationship(
        "User",
        backref=db.backref("feed_allowed_posts", lazy="dynamic"),
        foreign_keys=[user_id],
    )


class FeedPost(db.Model):
    __tablename__ = "feed_posts"

    id = db.Column(db.Integer, primary_key=True)

    author_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{USER_TBL}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = db.Column(db.String(240))
    html = db.Column(db.Text)

    # audience: 'all' | 'sector' | 'users'
    audience_type = db.Column(db.String(16), nullable=False, default="all", index=True)
    audience_id = db.Column(db.Integer, nullable=True, index=True)

    # ✅ TZ-aware UTC storage (fixes -1h / DST issues when formatted client-side)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),   # Python-side UTC default
        # If you're on Postgres and prefer DB-side default, use this instead:
        # server_default=db.text("(now() at time zone 'utc')")
    )

    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)

    # relationships
    author = db.relationship(
        "User",
        backref=db.backref("feed_posts", lazy="dynamic"),
        foreign_keys=[author_id],
    )

    comments = db.relationship(
        "FeedComment",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    reactions = db.relationship(
        "FeedReaction",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    attachments = db.relationship(
        "FeedAttachment",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    allowed_users = db.relationship(
        "FeedPostAllowedUser",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    # (Optional) handy helper if you serialize manually:
    def created_at_utc_iso(self) -> str:
        """Return ISO-8601 in UTC with 'Z' suffix."""
        return self.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    # NEW helper: set allowed users for audience_type = "users"
    def set_allowed_users(self, user_ids, include_author: bool = True) -> None:
        """
        Replace the allowed_users list with the given user_ids.

        NOTE: self.id must be set (object flushed / persisted) before calling.
        """
        from app.extensions import db as _db  # reuse the same db session

        # Normalize to unique int IDs
        ids = set()
        if include_author and self.author_id:
            try:
                ids.add(int(self.author_id))
            except (TypeError, ValueError):
                pass

        for val in (user_ids or []):
            try:
                ids.add(int(val))
            except (TypeError, ValueError):
                continue

        # Clear existing allowed_users
        if self.allowed_users is not None:
            try:
                # dynamic relationship -> Query
                self.allowed_users.delete(synchronize_session=False)
            except TypeError:
                # non-dynamic fallback
                for rel in list(self.allowed_users or []):
                    _db.session.delete(rel)

        # Insert new rows
        for uid in ids:
            _db.session.add(FeedPostAllowedUser(post_id=self.id, user_id=uid))



class FeedAttachment(db.Model):
    __tablename__ = "feed_attachments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("feed_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(128))
    file_size = db.Column(db.Integer)
    file_url = db.Column(db.String(500), nullable=False)
    preview_url = db.Column(db.String(500))

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    post = db.relationship(
        "FeedPost",
        back_populates="attachments",
        foreign_keys=[post_id],
    )


class FeedComment(db.Model):
    __tablename__ = "feed_comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("feed_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{USER_TBL}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    html = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    post = db.relationship(
        "FeedPost",
        back_populates="comments",
        foreign_keys=[post_id],
    )
    author = db.relationship(
        "User",
        backref=db.backref("feed_comments", lazy="dynamic"),
        foreign_keys=[author_id],
    )


class FeedReaction(db.Model):
    __tablename__ = "feed_reactions"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("feed_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{USER_TBL}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    emoji = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    post = db.relationship(
        "FeedPost",
        back_populates="reactions",
        foreign_keys=[post_id],
    )
    user = db.relationship(
        "User",
        backref=db.backref("feed_reactions", lazy="dynamic"),
        foreign_keys=[user_id],
    )

class FeedPinnedPost(db.Model):
    __tablename__ = "feed_pins"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("feed_posts.id"), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_feed_pin_user_post"),
    )