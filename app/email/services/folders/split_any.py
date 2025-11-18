# app/email/services/folders/split_any.py
import re

def split_any(path: str) -> list[str]:
    """
    Split user-entered path on '/', '.' or multiple separators.
    """
    return [p for p in re.split(r"[/.]+", path or "") if p.strip()]
