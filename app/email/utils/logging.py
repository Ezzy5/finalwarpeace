# app/email/utils/logging.py
"""
Helper for recording audit logs for EmailConnection.
"""
from datetime import datetime
from app.extensions import db
from app.email.models.connection import EmailConnectionLog


def log_event(connection_id: int, event: str, detail: str = ""):
    log = EmailConnectionLog(
        connection_id=connection_id,
        event=event,
        detail=detail,
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
