# app/email/models/__init__.py
"""
SQLAlchemy models for the Email feature.
"""
from .connection import EmailConnection, EmailConnectionLog

__all__ = [
    "EmailConnection",
    "EmailConnectionLog",
]
