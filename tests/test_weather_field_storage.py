import hashlib

import pytest

from app.spatial_fields.storage import (
    ImmutableObjectConflict,
    LocalFieldObjectStorage,
    MemoryFieldObjectStorage,
    S3FieldObjectStorage,
    validate_object_key,
)
from app.spatial_fields.monitoring import _health_tile_sample


@pytest.mark.parametrize(
    "key", ["", "/absolute", "../escape", "scope/../escape", "scope\\tile"]
)
def test_field_storage_rejects_unsafe_keys(key: str) -> None:
    with pytest.raises(ValueError):
        validate_object_key(key)


def test_memory_storage_is_idempotent_but_immutable() -> None:
    storage = MemoryFieldObjectStorage(public_base_url="https://cdn.example/fields")
    first = storage.put_immutable("europe/run/manifest.json", b"one")
    repeated = storage.put_immutable("europe/run/manifest.json", b"one")

    assert first == repeated
    assert first.sha256 == hashlib.sha256(b"one").hexdigest()
    assert first.public_url == "https://cdn.example/fields/europe/run/manifest.json"
    with pytest.raises(ImmutableObjectConflict):
        storage.put_immutable("europe/run/manifest.json", b"two")


def test_local_storage_publishes_complete_files_atomically(tmp_path) -> None:
    storage = LocalFieldObjectStorage(
        tmp_path / "fields", public_base_url="/weather-fields"
    )
    stored = storage.put_immutable("europe/run/assets/4/8/5.swf2.gz", b"payload")

    assert storage.exists(stored.key)
    assert storage.get(stored.key) == b"payload"
    assert stored.public_url == "/weather-fields/europe/run/assets/4/8/5.swf2.gz"
    assert not list((tmp_path / "fields").rglob(".field-upload-*"))


class _S3Error(Exception):
    def __init__(self, status: int, code: str):
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": status},
            "Error": {"Code": code},
        }


class _Body:
    def __init__(self, data: bytes):
        self.data = data

    def read(self) -> bytes:
        return self.data


class _S3Client:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.last_put: dict | None = None

    def put_object(self, **kwargs) -> None:
        identity = (kwargs["Bucket"], kwargs["Key"])
        if identity in self.objects:
            raise _S3Error(412, "PreconditionFailed")
        self.objects[identity] = bytes(kwargs["Body"])
        self.last_put = kwargs

    def get_object(self, **kwargs) -> dict:
        return {"Body": _Body(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    def head_object(self, **kwargs) -> dict:
        if (kwargs["Bucket"], kwargs["Key"]) not in self.objects:
            raise _S3Error(404, "NoSuchKey")
        return {}

    def delete_object(self, **kwargs) -> None:
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)


def test_s3_storage_is_conditional_immutable_and_cdn_addressable() -> None:
    client = _S3Client()
    storage = S3FieldObjectStorage(
        bucket="fields",
        key_prefix="production",
        public_base_url="https://forecast.example.com/data",
        client=client,
    )

    first = storage.put_immutable("europe/run/manifest.json", b"one")
    repeated = storage.put_immutable("europe/run/manifest.json", b"one")

    assert first == repeated
    assert first.public_url == "https://forecast.example.com/data/europe/run/manifest.json"
    assert storage.exists(first.key)
    assert storage.get(first.key) == b"one"
    assert client.last_put["IfNoneMatch"] == "*"
    assert client.last_put["CacheControl"] == "public, max-age=31536000, immutable"
    assert client.last_put["Metadata"]["sha256"] == first.sha256
    with pytest.raises(ImmutableObjectConflict):
        storage.put_immutable(first.key, b"two")

    storage.delete(first.key)
    assert not storage.exists(first.key)


def test_fast_health_uses_bounded_representative_tile_sample() -> None:
    assets = list(range(1000))

    assert _health_tile_sample(assets, deep=False) == [0, 500, 999]
    assert _health_tile_sample(assets, deep=True) == assets
