# app/notifications/models.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
from zoneinfo import ZoneInfo

from sqlalchemy import Text
from sqlalchemy.types import JSON as SA_JSON
try:
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
except Exception:  # pragma: no cover
    PG_JSONB = None  # type: ignore

from app.extensions import db

# Portable JSON -> JSONB on Postgres, JSON on others
if PG_JSONB is not None:
    META_TYPE = SA_JSON().with_variant(PG_JSONB(astext_type=Text()), 'postgresql')
else:
    META_TYPE = SA_JSON()

def _app_tz() -> ZoneInfo:
    try:
        from flask import current_app
        name = current_app.config.get("APP_TIMEZONE", "Europe/Skopje")
    except Exception:
        name = "Europe/Skopje"
    return ZoneInfo(name)

def _iso_local(dt: datetime) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_app_tz()).isoformat()

def _iso_utc_z(dt: datetime) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)

    # ✅ make sure we NEVER insert NULL here
    kind = db.Column(db.String(64), nullable=False, default="generic")

    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(1024), nullable=True)
    meta = db.Column(META_TYPE, nullable=True)

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    # stored as naive UTC
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        created = self.created_at or datetime.utcnow()
        return {
            "id": self.id,
            "user_id": self.user_id,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "link_url": self.link_url,
            "meta": self.meta or {},
            "is_read": self.is_read,

            # timezone-safe outputs for UI
            "created_at_local": _iso_local(created),
            "created_at_utc": _iso_utc_z(created),

            # legacy
            "created_at": created.isoformat(),
        }
