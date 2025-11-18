# app/email/services/connection.py
import imaplib, poplib, smtplib, ssl

def _ssl_ctx():
    return ssl.create_default_context()

# ---- IMAP ----
def open_imap(cfg: dict):
    host = cfg["incoming_host"]
    port = int(cfg["incoming_port"])
    sec  = (cfg.get("incoming_security") or "ssl").lower()

    if sec in {"ssl", "tls"} or port == 993:
        conn = imaplib.IMAP4_SSL(host, port, ssl_context=_ssl_ctx())
    else:
        conn = imaplib.IMAP4(host, port)
        if sec == "starttls" or port == 143:
            conn.starttls(ssl_context=_ssl_ctx())
    conn.login(cfg["email_address"], cfg.get("password", ""))
    return conn

# ---- POP3 ----
def open_pop3(cfg: dict):
    host = cfg["incoming_host"]
    port = int(cfg["incoming_port"])
    sec  = (cfg.get("incoming_security") or "ssl").lower()

    if sec in {"ssl", "tls"} or port == 995:
        conn = poplib.POP3_SSL(host, port)
    else:
        conn = poplib.POP3(host, port)
        # POP3 STARTTLS is uncommon and not standardized—omit
    conn.user(cfg["email_address"])
    conn.pass_(cfg.get("password", ""))
    return conn

# ---- SMTP ----
def open_smtp(cfg: dict):
    import smtplib, ssl
    host = cfg["outgoing_host"]
    port = int(cfg["outgoing_port"])
    sec  = (cfg.get("outgoing_security") or "").lower()

    if sec in {"ssl", "tls"} or port == 465:
        ctx = ssl.create_default_context()
        server = smtplib.SMTP_SSL(host, port, timeout=8, context=ctx)
        server.ehlo()
    else:
        server = smtplib.SMTP(host, port, timeout=8)
        server.ehlo()
        if sec == "starttls" or port == 587:
            ctx = ssl.create_default_context()
            server.starttls(context=ctx)
            server.ehlo()

    server.login(cfg["email_address"], cfg.get("password", ""))
    return server
