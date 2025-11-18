# app/email/utils/encryption.py
"""
Encrypt / decrypt secrets for email accounts using Fernet (AES128 + HMAC).
Accepts SECRET_ENCRYPTION_KEY (a Fernet key) or derives one from SECRET_KEY.
"""
from __future__ import annotations
import base64, hashlib
from cryptography.fernet import Fernet
from flask import current_app


def _derive_fernet_key_from_secret(secret: str) -> bytes:
    # 32 raw bytes from SHA-256, then urlsafe base64 encode → valid Fernet key
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)  # 44-byte base64 string


def _get_key() -> bytes:
    """
    Return a valid Fernet key (32 url-safe base64-encoded bytes).
    Priority:
      1) app.config["SECRET_ENCRYPTION_KEY"] (already a Fernet key)
      2) Derive from app.config["SECRET_KEY"] (stable fallback)
    """
    cfg_key = current_app.config.get("SECRET_ENCRYPTION_KEY")
    if cfg_key:
        # If it already looks like a Fernet key, use it; if not, derive from it.
        if isinstance(cfg_key, str):
            raw = cfg_key.encode("utf-8")
        else:
            raw = bytes(cfg_key)
        try:
            # Validate
            Fernet(raw)
            return raw
        except Exception:
            # Not a Fernet key → derive one deterministically
            return _derive_fernet_key_from_secret(cfg_key if isinstance(cfg_key, str) else raw.decode("utf-8"))

    # Fallback: derive from Flask SECRET_KEY
    secret_key = current_app.config.get("SECRET_KEY", "dev-only")
    return _derive_fernet_key_from_secret(secret_key)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    f = Fernet(_get_key())
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    f = Fernet(_get_key())
    return f.decrypt(token.encode("utf-8")).decode("utf-8")
