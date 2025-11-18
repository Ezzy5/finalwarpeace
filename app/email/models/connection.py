# app/email/models/connection.py
from datetime import datetime
from app.extensions import db


class EmailConnection(db.Model):
    """
    Stores a connected email account for a user.
    Supports IMAP, POP3, or OAuth modes.
    """
    __tablename__ = "email_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    provider = db.Column(db.String(50), nullable=False)   # gmail / outlook / yahoo / custom
    mode = db.Column(db.String(20), nullable=False)       # oauth / imap / pop3

    email_address = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255))
    reply_to = db.Column(db.String(255))

    # Incoming
    incoming_host = db.Column(db.String(255))
    incoming_port = db.Column(db.Integer)
    incoming_security = db.Column(db.String(20))

    # Outgoing
    outgoing_host = db.Column(db.String(255))
    outgoing_port = db.Column(db.Integer)
    outgoing_security = db.Column(db.String(20))
    outgoing_auth_custom = db.Column(db.Boolean, default=False)

    # Security & policy
    certificate_policy = db.Column(db.String(20), default="strict")  # strict / allow_self_signed / none
    secret_ref = db.Column(db.String(255))  # encrypted password or token

    # Advanced
    use_idle = db.Column(db.Boolean, default=True)
    sync_window_days = db.Column(db.Integer, default=30)

    # Status
    status = db.Column(db.String(20), default="error")  # connected / error / revoked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_verified_at = db.Column(db.DateTime)

    # Relationships
    logs = db.relationship("EmailConnectionLog", backref="connection", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EmailConnection {self.email_address} ({self.provider}/{self.mode})>"


class EmailConnectionLog(db.Model):
    """
    Audit log for connection events (verify success/fail, token refresh, etc.)
    """
    __tablename__ = "email_connection_logs"

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("email_connections.id"), nullable=False)

    event = db.Column(db.String(100), nullable=False)   # e.g., "verify_success", "verify_fail", "token_refresh"
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<EmailConnectionLog {self.event} @ {self.created_at}>"
