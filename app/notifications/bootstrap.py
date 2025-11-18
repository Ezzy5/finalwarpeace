from __future__ import annotations
from typing import Set

from sqlalchemy import text
from app.extensions import db
from .models import Notification

def _sqlite_columns(table: str) -> Set[str]:
    rows = db.session.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
    return {row[1] for row in rows}  # row[1] == column name

def ensure_sqlite_schema() -> None:
    """Idempotent schema guard for SQLite only."""
    eng = db.engine
    if eng.dialect.name != "sqlite":
        return

    # 1) Ensure table exists (this won't add new columns to an existing table)
    Notification.__table__.create(bind=eng, checkfirst=True)

    cols = _sqlite_columns("notifications")

    # 2) Add 'kind' column if it doesn't exist
    if "kind" not in cols:
        db.session.execute(text(
            "ALTER TABLE notifications "
            "ADD COLUMN kind VARCHAR(64) NOT NULL DEFAULT 'generic'"
        ))
        db.session.commit()
        cols.add("kind")

    # 3) Ensure 'meta' is non-null (fill nulls with '{}')
    if "meta" in cols:
        db.session.execute(text(
            "UPDATE notifications SET meta='{}' "
            "WHERE meta IS NULL"
        ))
        db.session.commit()

    # 4) Ensure index on user_id
    # SQLite: IF NOT EXISTS works here
    db.session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_id "
        "ON notifications (user_id)"
    ))
    db.session.commit()
