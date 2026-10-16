"""Static delivery for immutable weather-field assets."""

from __future__ import annotations

from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send


class ImmutableFieldStaticFiles(StaticFiles):
    """Serve content-addressed field objects with long-lived browser caching."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def immutable_send(message):
            if message["type"] == "http.response.start" and message["status"] == 200:
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"public, max-age=31536000, immutable"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await super().__call__(scope, receive, immutable_send)
