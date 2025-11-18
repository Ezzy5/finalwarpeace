# app/feed/routes/__init__.py
import pkgutil
import importlib

__all__ = []

for _, module_name, _ in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{module_name}")
    __all__.append(module_name)
