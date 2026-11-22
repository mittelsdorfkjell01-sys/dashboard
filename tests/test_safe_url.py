from __future__ import annotations

import socket

import pytest

from app.media.safe_url import UnsafeOutboundUrl, require_public_https_url


def _dns(monkeypatch, *addresses: str) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
            for address in addresses
        ],
    )


def test_safe_url_accepts_a_public_https_host(monkeypatch):
    _dns(monkeypatch, "93.184.216.34")
    assert require_public_https_url("https://example.com/photo.jpg") == "https://example.com/photo.jpg"


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fe80::1"],
)
def test_safe_url_rejects_non_public_addresses(monkeypatch, address):
    _dns(monkeypatch, address)
    with pytest.raises(UnsafeOutboundUrl):
        require_public_https_url("https://images.example/photo.jpg")


def test_safe_url_rejects_http_credentials_and_custom_ports(monkeypatch):
    _dns(monkeypatch, "93.184.216.34")
    for url in (
        "http://example.com/photo.jpg",
        "https://user@example.com/photo.jpg",
        "https://example.com:8443/photo.jpg",
        "https://example.com:invalid/photo.jpg",
    ):
        with pytest.raises(UnsafeOutboundUrl):
            require_public_https_url(url)
