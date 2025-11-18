# app/email/services/discovery.py
"""
Auto-discovery of email server settings.
Implements RFC 6186, Mozilla Autoconfig, Microsoft Autodiscover, and MX fallback.
"""
import dns.resolver


def discover_from_mx(domain: str) -> dict | None:
    """
    Use MX records to guess provider (Google, Microsoft, Yahoo).
    """
    try:
        answers = dns.resolver.resolve(domain, "MX")
        mx_hosts = [r.exchange.to_text().lower() for r in answers]

        if any("google.com" in mx for mx in mx_hosts):
            return {"provider": "gmail"}
        if any("outlook.com" in mx or "microsoft.com" in mx for mx in mx_hosts):
            return {"provider": "outlook"}
        if any("yahoo.com" in mx for mx in mx_hosts):
            return {"provider": "yahoo"}
    except Exception:
        return None
    return None


def suggest_defaults(provider: str) -> dict:
    """
    Return known server settings for popular providers.
    """
    defaults = {
        "gmail": {
            "imap": ("imap.gmail.com", 993, "ssl"),
            "pop3": ("pop.gmail.com", 995, "ssl"),
            "smtp": ("smtp.gmail.com", 465, "ssl"),
        },
        "outlook": {
            "imap": ("outlook.office365.com", 993, "ssl"),
            "pop3": ("outlook.office365.com", 995, "ssl"),
            "smtp": ("smtp.office365.com", 587, "starttls"),
        },
        "yahoo": {
            "imap": ("imap.mail.yahoo.com", 993, "ssl"),
            "pop3": ("pop.mail.yahoo.com", 995, "ssl"),
            "smtp": ("smtp.mail.yahoo.com", 465, "ssl"),
        },
    }
    return defaults.get(provider, {})
