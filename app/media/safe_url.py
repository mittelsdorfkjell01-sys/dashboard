"""Validation for outbound requests to stored, operator-supplied URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeOutboundUrl(ValueError):
    pass


def require_public_https_url(url: str) -> str:
    """Return a normalized URL only when every resolved address is public.

    Redirect targets must be passed through this function again.  Credentials,
    fragments and non-default ports are rejected to keep parsing unambiguous.
    """
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeOutboundUrl("URL could not be parsed safely") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UnsafeOutboundUrl("only public HTTPS URLs are allowed")
    if parsed.username or parsed.password or parsed.fragment:
        raise UnsafeOutboundUrl("URL credentials and fragments are not allowed")
    if port not in (None, 443):
        raise UnsafeOutboundUrl("non-standard URL ports are not allowed")

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname, 443, type=socket.SOCK_STREAM
            )
        }
    except (OSError, UnicodeError) as exc:
        raise UnsafeOutboundUrl("URL host could not be resolved") from exc
    if not addresses:
        raise UnsafeOutboundUrl("URL host has no addresses")
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            raise UnsafeOutboundUrl("URL resolves to a non-public address")
    return parsed.geturl()
