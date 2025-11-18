# app/email/routes/__init__.py

"""
Routes package for the Email feature.
Each step of the flow is isolated in its own module:
- provider.py   → /email
- protocol.py   → /email/protocol
- config.py     → /email/config
- verify.py     → /email/verify
- status.py     → /email/status
"""

# Explicit imports ensure that when this package is imported,
# each module's routes get registered with the blueprint.
from . import provider, protocol, config, verify, status, mailbox, compose, dnd_move , attachments, folder_delete, mail_actions

__all__ = [
    "provider",
    "protocol",
    "config",
    "verify",
    "status",
    "mailbox","compose", "dnd_move ", "folders  ", " attachments", "folder_delete", "mail_actions"
]
