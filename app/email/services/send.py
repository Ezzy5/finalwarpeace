# app/email/services/send.py
import smtplib, ssl, os
from email.message import EmailMessage

def send_email(cfg: dict, to_addr: str, subject: str, body: str, attachments=None, is_html=False):
    msg = EmailMessage()
    msg["From"] = cfg.get("email_address")
    msg["To"] = to_addr
    msg["Subject"] = subject
    if is_html:
        msg.set_content(body, subtype="html")
    else:
        msg.set_content(body)

    if attachments:
        for path in attachments:
            with open(path, "rb") as f:
                data = f.read()
                msg.add_attachment(
                    data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=os.path.basename(path),
                )

    # choose SSL or STARTTLS based on cfg (handled in connection.open_smtp)
    from .connection import open_smtp
    server = open_smtp(cfg)
    server.send_message(msg)
    server.quit()
    return {"ok": True, "detail": f"Sent to {to_addr}"}
