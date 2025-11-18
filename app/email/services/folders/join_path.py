# app/email/services/folders/join_path.py
def join_path(parts: list[str], delim: str) -> str:
    parts = [p for p in parts if p and str(p).strip()]
    return delim.join(parts)
