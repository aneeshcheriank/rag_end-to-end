"""Service-facing config entry point.

Re-exports the shared settings from ``src.config`` so the ``app`` package has a
stable place to import configuration as the service layers (db, api, auth) are
added in later phases.
"""

from src.config import Settings, settings

__all__ = ["Settings", "settings"]
