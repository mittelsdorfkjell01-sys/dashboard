"""Wikimedia thumbnail proxy checks that do not need a database."""

from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from app.api import admin_media
from app.config import get_settings


@pytest.mark.parametrize("url", [
    "https://upload.wikimedia.org.evil.example/wikipedia/commons/thumb/x.jpg",
    "http://127.0.0.1/internal",
    "https://upload.wikimedia.org:443/wikipedia/commons/thumb/x.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/x.jpg?redirect=1",
])
def test_rejects_untrusted_thumbnail_urls(monkeypatch, url):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("invalid URL must never be fetched")

    monkeypatch.setattr(admin_media.httpx, "stream", unexpected_request)
    with pytest.raises(HTTPException) as error:
        admin_media.wikimedia_thumbnail(url)
    assert error.value.status_code == 400


def test_fetches_wikimedia_thumbnail_with_descriptive_user_agent(monkeypatch):
    requests = []

    class ThumbnailResponse:
        headers = {"content-type": "image/jpeg", "content-length": "4"}

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size):
            yield b"jpeg"

    @contextmanager
    def fake_stream(method, url, **kwargs):
        requests.append((method, url, kwargs))
        yield ThumbnailResponse()

    monkeypatch.setattr(admin_media.httpx, "stream", fake_stream)
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/photo.jpg/500px-photo.jpg"
    response = admin_media.wikimedia_thumbnail(url)

    assert response.status_code == 200
    assert response.body == b"jpeg"
    assert response.media_type == "image/jpeg"
    assert requests[0][0:2] == ("GET", url)
    assert requests[0][2]["follow_redirects"] is False
    assert requests[0][2]["headers"]["User-Agent"] == get_settings().wikimedia_user_agent
