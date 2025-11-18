# app/users/routes/__init__.py
"""
Auto-import all route modules in this package so their @bp.route decorators
register on the users blueprint. No manual list to maintain.
"""
from __future__ import annotations
import logging
import pkgutil
from importlib import import_module
from contextlib import suppress

log = logging.getLogger(__name__)

def _safe_import(modname: str) -> None:
    """Import .<modname> and never crash the app if one module fails."""
    try:
        import_module(f"{__name__}.{modname}")
        log.debug("users.routes: imported %s", modname)
    except Exception as e:
        log.warning("users.routes: failed to import %s: %s", modname, e)

def load_routes() -> None:
    """
    1) Import helpers (if present).
    2) Import 'panel' first so /users/panel is ready.
    3) Auto-discover and import all other .py files in this package.
    """
    # 1) helpers (utility funcs only; no routes required)
    with suppress(Exception):
        import_module(f"{__name__}.helpers")

    # 2) import panel early if it exists
    with suppress(Exception):
        _safe_import("panel")

    # 3) auto-import everything else in this package
    for _finder, name, ispkg in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        if ispkg:
            continue
        if name.startswith("_"):
            continue
        if name in {"helpers", "panel"}:
            continue
        _safe_import(name)
