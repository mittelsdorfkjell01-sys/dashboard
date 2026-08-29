"""Media garbage collection, provider audit and retry checks."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import delete, select

from app.config import get_settings
from app.media import gc as media_gc
from app.media import storage
from app.media.gc import (
    audit_blob_orphans,
    collect_media_garbage,
    media_lock_identity,
    schedule_media_gc,
)
from app.models import MediaGarbageCandidate, MediaGcState


def test_content_digest_is_the_shared_upload_and_delete_lock_identity():
    digest = "a" * 64
    url = (
        "https://store.public.blob.vercel-storage.com/"
        f"images/aa/{digest}-responsive-480_768.avif"
    )
    assert media_lock_identity(digest) == media_lock_identity(url) == digest


def test_blob_list_uses_bounded_cursor_api(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "blob")
    monkeypatch.setattr(settings, "blob_read_write_token", "test-token")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "blobs": [
                    {
                        "url": "https://store.public.blob.vercel-storage.com/images/a.avif",
                        "pathname": "images/a.avif",
                        "size": 123,
                        "uploadedAt": "2026-08-01T12:00:00.000Z",
                    }
                ],
                "cursor": "next-page",
                "hasMore": True,
            }

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(httpx, "get", fake_get)
    page = storage.list_blob_objects(prefix="images/", limit=5000, cursor="page-1")

    assert captured["url"] == "https://vercel.com/api/blob"
    assert captured["params"] == {
        "prefix": "images/",
        "limit": 1000,
        "cursor": "page-1",
    }
    assert captured["headers"]["authorization"] == "Bearer test-token"
    assert captured["headers"]["x-api-version"] == "11"
    assert page["items"][0]["uploaded_at"].tzinfo is not None
    assert page["has_more"] is True


def test_blob_delete_surfaces_provider_failure_for_retry(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "blob")
    monkeypatch.setattr(settings, "blob_read_write_token", "test-token")

    def fake_post(url, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(RuntimeError, match="delete failed"):
        storage.delete_candidate_strict(
            "https://store.public.blob.vercel-storage.com/images/a.avif",
            delete_set=False,
            media_dir="unused",
            url_prefix="/media",
        )


def test_local_unreferenced_candidate_is_deleted_after_grace(
    db, tmp_path, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    monkeypatch.setattr(settings, "media_url_prefix", "/media")
    relative = "images/gc-delete.avif"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    url = f"/media/{relative}"

    assert schedule_media_gc(db, url, grace_hours=1)
    result = collect_media_garbage(
        db,
        now=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    assert result["deleted"] == 1
    assert not target.exists()
    assert db.scalar(
        select(MediaGarbageCandidate).where(MediaGarbageCandidate.url == url)
    ) is None


def test_locked_reference_recheck_cancels_delete(db, tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    monkeypatch.setattr(settings, "media_url_prefix", "/media")
    relative = "images/gc-keep.avif"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"shared")
    url = f"/media/{relative}"
    assert schedule_media_gc(db, url, grace_hours=1)
    monkeypatch.setattr(
        "app.media.lifecycle.image_url_is_referenced",
        lambda _db, _url, **_kwargs: True,
    )

    result = collect_media_garbage(
        db,
        now=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    assert result["cancelled"] == 1
    assert target.exists()
    assert db.scalar(
        select(MediaGarbageCandidate).where(MediaGarbageCandidate.url == url)
    ) is None


def test_content_upload_commit_wins_against_concurrent_collector(
    db, tmp_path, monkeypatch
):
    """The collector cannot delete between object PUT and reference commit."""
    from app.db.session import SessionLocal

    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    monkeypatch.setattr(settings, "media_url_prefix", "/media")
    digest = "b" * 64
    relative = f"images/bb/{digest}-responsive-none.avif"
    url = f"/media/{relative}"
    target = tmp_path / relative
    assert schedule_media_gc(db, url, grace_hours=1)

    upload_db = SessionLocal()
    original_lock = media_gc.acquire_media_lock
    collector_waiting = threading.Event()

    def observed_lock(session, value):
        if threading.current_thread().name.startswith("gc-race"):
            collector_waiting.set()
        return original_lock(session, value)

    def collect_in_other_transaction():
        with SessionLocal() as collector_db:
            return collect_media_garbage(
                collector_db,
                now=datetime.now(timezone.utc) + timedelta(hours=2),
            )

    try:
        # This is the same identity acquire_image_set_lock derives before PUT.
        original_lock(upload_db, digest)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"new upload")
        monkeypatch.setattr(media_gc, "acquire_media_lock", observed_lock)
        with ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="gc-race",
        ) as executor:
            future = executor.submit(collect_in_other_transaction)
            assert collector_waiting.wait(timeout=5)
            assert not future.done()

            media_gc.register_media_reference(upload_db, url)
            upload_db.commit()
            result = future.result(timeout=5)
    finally:
        upload_db.close()

    assert result == {"due": 1, "deleted": 0, "cancelled": 0, "failed": 0}
    assert target.exists()
    assert db.scalar(
        select(MediaGarbageCandidate).where(MediaGarbageCandidate.url == url)
    ) is None


def test_failed_delete_is_retained_with_backoff(db, tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    monkeypatch.setattr(settings, "media_url_prefix", "/media")
    url = "/media/images/gc-retry.avif"
    assert schedule_media_gc(db, url, grace_hours=1)
    monkeypatch.setattr(
        storage,
        "delete_candidate_strict",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("temporary")),
    )
    current = datetime.now(timezone.utc) + timedelta(hours=2)

    result = collect_media_garbage(db, now=current)
    candidate = db.scalar(
        select(MediaGarbageCandidate).where(MediaGarbageCandidate.url == url)
    )

    assert result["failed"] == 1
    assert candidate.attempts == 1
    assert candidate.last_error == "RuntimeError: temporary"
    assert candidate.not_before > current
    db.delete(candidate)
    db.commit()


def test_blob_audit_is_resumable_complete_and_groups_responsive_sets(
    db, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "blob")
    now = datetime.now(timezone.utc)
    digest = "a" * 64
    base = (
        "https://store.public.blob.vercel-storage.com/"
        f"images/aa/{digest}-responsive-480_768.avif"
    )
    spot_url = "https://store.public.blob.vercel-storage.com/spots/old/hero.avif"
    region_url = (
        "https://store.public.blob.vercel-storage.com/regions/old/hero.avif"
    )
    expected_urls = {base, spot_url, region_url}
    state_keys = {"blob:images", "blob:spots", "blob:regions"}
    calls = []

    def fake_list(*, prefix, limit, cursor=None):
        calls.append((prefix, limit, cursor))
        urls = {
            "images/": [base, base.replace(".avif", "-w480.avif")],
            "spots/": [spot_url],
            "regions/": [region_url],
        }[prefix]
        return {
            "items": [
                {
                    "url": url,
                    "uploaded_at": now - timedelta(days=2),
                    "pathname": url.rsplit("/", 1)[-1],
                    "size": 1,
                }
                for url in urls
            ],
            "cursor": None,
            "has_more": False,
        }

    monkeypatch.setattr(storage, "list_blob_objects", fake_list)
    try:
        result = audit_blob_orphans(db, limit=25, now=now)
        candidates = list(
            db.scalars(
                select(MediaGarbageCandidate).where(
                    MediaGarbageCandidate.url.in_(expected_urls)
                )
            ).all()
        )

        assert [call[0] for call in calls] == ["images/", "spots/", "regions/"]
        assert result == {"scanned": 4, "queued": 3, "has_more": False}
        assert len(candidates) == 3
        assert all(candidate.delete_set for candidate in candidates)
        assert {
            state.backend
            for state in db.scalars(
                select(MediaGcState).where(MediaGcState.backend.in_(state_keys))
            )
        } == state_keys
    finally:
        db.execute(
            delete(MediaGarbageCandidate).where(
                MediaGarbageCandidate.url.in_(expected_urls)
            )
        )
        db.execute(delete(MediaGcState).where(MediaGcState.backend.in_(state_keys)))
        db.commit()
