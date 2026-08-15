"""Remote-write guard: refuse admin-surface mutations when a non-production app
is pointed at a remote (production-like) database.

This is the server-side half of the local/prod safety net (the back office also
renders a permanent banner). It intentionally guards only the ``/admin`` write
surface: reads stay allowed (inspecting production is fine) and ``/auth`` login
keeps working so an operator can still sign in and look — just not mutate.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

_MESSAGE = (
    "Schreibzugriff blockiert: Diese nicht-produktive Umgebung ist mit einer "
    "Produktions-Datenbank verbunden. Setze DATABASE_URL auf eine lokale "
    "Datenbank — oder ALLOW_REMOTE_WRITES=true, wenn das beabsichtigt ist."
)


class RemoteWriteGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and request.url.path.startswith("/admin"):
            if get_settings().admin_writes_blocked:
                return JSONResponse({"detail": _MESSAGE}, status_code=403)
        return await call_next(request)
