# app/email/services/move/quote.py
def quote_folder(name: str) -> str:
    """
    IMAP folder names should be quoted if they contain spaces or special chars.
    """
    if name is None:
        return '""'
    s = str(name)
    if s.startswith('"') and s.endswith('"'):
        return s
    return f'"{s}"'
