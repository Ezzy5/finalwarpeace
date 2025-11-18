# app/email/services/folders/quote.py
def quote_folder(name: str) -> str:
    s = (name or "").strip()
    if s.startswith('"') and s.endswith('"'):
        return s
    return f'"{s}"'
