"""Origin and double-submit CSRF protection for cookie-authenticated writes."""

from __future__ import annotations

import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SESSION_START_PATHS = {"/auth/login", "/account/login", "/account/register"}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response, token: str | None = None) -> str:
    settings = get_settings()
    token = token or new_csrf_token()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=max(settings.jwt_ttl_hours, settings.app_jwt_ttl_hours) * 3600,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return token


def clear_csrf_cookie(response) -> None:
    response.delete_cookie(get_settings().csrf_cookie_name, path="/")


def _allowed_origins(request: Request) -> set[str]:
    settings = get_settings()
    forwarded = request.headers.get("x-forwarded-proto")
    scheme = forwarded.split(",")[0].strip() if forwarded else request.url.scheme
    host = request.headers.get("host")
    origins = set(settings.cors_origins)
    if host:
        origins.add(f"{scheme}://{host}")
    return origins


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        has_auth_cookie = bool(
            request.cookies.get(settings.auth_cookie_name)
            or request.cookies.get(settings.app_auth_cookie_name)
        )
        starts_session = request.url.path.rstrip("/") in SESSION_START_PATHS
        if request.method not in SAFE_METHODS and (has_auth_cookie or starts_session):
            origin = request.headers.get("origin")
            if origin and origin not in _allowed_origins(request):
                return JSONResponse({"detail": "Ungültiger Request-Ursprung."}, status_code=403)
            if settings.app_env == "production" and not origin:
                return JSONResponse({"detail": "Request-Ursprung fehlt."}, status_code=403)
            if has_auth_cookie and not starts_session:
                cookie_token = request.cookies.get(settings.csrf_cookie_name)
                header_token = request.headers.get("x-csrf-token")
                if not (
                    cookie_token
                    and header_token
                    and secrets.compare_digest(cookie_token, header_token)
                ):
                    return JSONResponse({"detail": "CSRF-Prüfung fehlgeschlagen."}, status_code=403)
        return await call_next(request)
