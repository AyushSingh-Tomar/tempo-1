"""``/api/v1`` router. Feature routers (processing runs, mappings, discrepancies,
reports, ...) are included into ``api_router`` by their owners."""

from bordereaux.api.v1.router import api_router

__all__ = ["api_router"]
