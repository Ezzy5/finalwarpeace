# app/email/utils/validators.py
"""
Custom validators for email configuration.
"""
import re


EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def is_valid_email(addr: str) -> bool:
    return bool(addr and EMAIL_REGEX.match(addr))


def is_valid_hostname(host: str) -> bool:
    """
    Simple check for host validity.
    """
    if not host:
        return False
    return all(re.match(r"^[A-Za-z0-9-]+$", label) for label in host.split(".") if label)


def is_valid_port(port: int) -> bool:
    return 1 <= int(port) <= 65535
