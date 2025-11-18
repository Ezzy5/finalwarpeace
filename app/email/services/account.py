# app/email/services/account.py
from app.email.utils.encryption import decrypt_secret

def build_runtime_cfg(conn) -> dict:
    """
    Convert EmailConnection model -> runtime config dict for services.
    Decrypts secret_ref to 'password'.
    """
    return {
        "email_address": conn.email_address,
        "password": decrypt_secret(conn.secret_ref or "") if conn.secret_ref else "",
        "incoming_host": conn.incoming_host,
        "incoming_port": conn.incoming_port,
        "incoming_security": (conn.incoming_security or "ssl").lower(),
        "outgoing_host": conn.outgoing_host,
        "outgoing_port": conn.outgoing_port,
        "outgoing_security": (conn.outgoing_security or "ssl").lower(),
    }
