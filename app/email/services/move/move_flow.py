# app/email/services/move/move_flow.py
from app.email.services.connection import open_imap
from app.email.services.account import build_runtime_cfg
from .supports_move import server_supports_move
from .try_uid_move import try_uid_move
from .copy_message import copy_message
from .mark_deleted import mark_deleted
from .expunge import expunge_mailbox

def move_message(conn_model, from_folder: str, uid: str, to_folder: str) -> dict:
    """
    Orchestrate moving a message. Tries UID MOVE; falls back to COPY + STORE + EXPUNGE.
    Returns { ok: bool, method: 'move'|'copy+delete', error?: str }
    """
    cfg = build_runtime_cfg(conn_model)
    imap = open_imap(cfg)
    try:
        # Select source folder first (for MOVE and STORE/EXPUNGE semantics)
        imap.select(from_folder, readonly=False)

        if server_supports_move(imap):
            if try_uid_move(imap, uid, to_folder):
                return {"ok": True, "method": "move"}
            # some servers lie; fall through

        # Fallback: COPY -> mark deleted -> expunge
        if not copy_message(imap, uid, to_folder):
            return {"ok": False, "method": "copy+delete", "error": "COPY failed"}
        if not mark_deleted(imap, uid):
            return {"ok": False, "method": "copy+delete", "error": "STORE +FLAGS \\Deleted failed"}
        if not expunge_mailbox(imap):
            # not fatal; many servers auto-expunge on close
            return {"ok": True, "method": "copy+delete"}  # soft success
        return {"ok": True, "method": "copy+delete"}
    except Exception as e:
        return {"ok": False, "method": "unknown", "error": str(e)}
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass
