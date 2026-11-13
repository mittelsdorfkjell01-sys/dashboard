from fastapi import Response

from app.api._http_cache import PUBLIC_CACHE_CONTROL, set_public_cache


def test_editable_public_content_has_a_bounded_stale_window() -> None:
    response = Response()
    set_public_cache(response)

    assert response.headers["Cache-Control"] == PUBLIC_CACHE_CONTROL
    assert "max-age=60" in PUBLIC_CACHE_CONTROL
    assert "s-maxage=300" in PUBLIC_CACHE_CONTROL
    assert "stale-while-revalidate=60" in PUBLIC_CACHE_CONTROL
    assert "stale-while-revalidate=86400" not in PUBLIC_CACHE_CONTROL
