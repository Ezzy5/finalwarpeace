# app/email/services/verification.py
"""
Verification logic for email connections.
Performs DNS, TCP, TLS, and authentication checks.
"""
import smtplib, imaplib, poplib, socket, ssl


def test_connection(config: dict) -> dict:
    """
    Test incoming + outgoing server connectivity.
    Returns dict with success flag and error (if any).
    """
    results = {
        "success": False,
        "incoming": None,
        "outgoing": None,
        "error": None,
    }

    try:
        proto = config.get("protocol", "imap")

        if proto == "imap":
            results["incoming"] = _test_imap(config)
        elif proto == "pop3":
            results["incoming"] = _test_pop3(config)
        else:
            results["incoming"] = {"ok": True, "detail": "OAuth deferred"}

        results["outgoing"] = _test_smtp(config)

        results["success"] = (
            results["incoming"]["ok"] and results["outgoing"]["ok"]
        )

    except Exception as e:
        results["error"] = str(e)

    return results


def _test_imap(cfg: dict) -> dict:
    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(cfg["incoming_host"], int(cfg["incoming_port"]), ssl_context=context)
        mail.login(cfg["email_address"], cfg.get("password", ""))
        mail.logout()
        return {"ok": True, "detail": "IMAP login OK"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def _test_pop3(cfg: dict) -> dict:
    try:
        pop = poplib.POP3_SSL(cfg["incoming_host"], int(cfg["incoming_port"]))
        pop.user(cfg["email_address"])
        pop.pass_(cfg.get("password", ""))
        pop.quit()
        return {"ok": True, "detail": "POP3 login OK"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def _test_smtp(cfg: dict) -> dict:
    import smtplib, ssl
    host = cfg["outgoing_host"]
    port = int(cfg["outgoing_port"])
    sec  = (cfg.get("outgoing_security") or "").lower()

    try:
        context = ssl.create_default_context()

        if sec in {"ssl", "tls"} or port == 465:
            # SMTPS: SSL from the start
            server = smtplib.SMTP_SSL(host, port, timeout=8, context=context)
            server.ehlo()
        else:
            # Plain or STARTTLS
            server = smtplib.SMTP(host, port, timeout=8)
            server.ehlo()
            if sec == "starttls" or port == 587:
                server.starttls(context=context)
                server.ehlo()

        server.login(cfg["email_address"], cfg.get("password", ""))
        server.quit()
        return {"ok": True, "detail": "SMTP login OK"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
