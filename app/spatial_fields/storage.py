"""Immutable object storage boundary for weather-field data-plane assets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any, Protocol
from urllib.parse import quote


class ImmutableObjectConflict(RuntimeError):
    """Raised when an existing immutable key has different content."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    sha256: str
    public_url: str


class FieldObjectStorage(Protocol):
    def put_immutable(self, key: str, data: bytes) -> StoredObject: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def public_url(self, key: str) -> str: ...

    def delete(self, key: str) -> None: ...


def validate_object_key(key: str) -> str:
    """Accept canonical URL-style relative keys and reject traversal/ambiguity."""
    if not key or "\\" in key or key.startswith("/"):
        raise ValueError("weather-field object key must be a relative POSIX path")
    path = PurePosixPath(key)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("weather-field object key contains an unsafe path segment")
    canonical = path.as_posix()
    if canonical != key:
        raise ValueError("weather-field object key must be canonical")
    return canonical


class LocalFieldObjectStorage:
    """Atomic, immutable local storage for development and self-hosted releases."""

    def __init__(self, root: str | Path, *, public_base_url: str):
        self.root = Path(root).resolve()
        self.public_base_url = public_base_url.rstrip("/")
        if not self.public_base_url:
            raise ValueError("public_base_url must not be empty")

    def _path(self, key: str) -> Path:
        canonical = validate_object_key(key)
        target = (self.root / Path(*PurePosixPath(canonical).parts)).resolve()
        if os.path.commonpath((self.root, target)) != str(self.root):
            raise ValueError("weather-field object key escaped the storage root")
        return target

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{validate_object_key(key)}"

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def put_immutable(self, key: str, data: bytes) -> StoredObject:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256(data).hexdigest()
        if target.exists():
            existing = target.read_bytes()
            if hashlib.sha256(existing).hexdigest() != checksum:
                raise ImmutableObjectConflict(
                    f"immutable weather-field key already exists with different content: {key}"
                )
            return StoredObject(key, len(existing), checksum, self.public_url(key))

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".field-upload-", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                existing = target.read_bytes()
                if hashlib.sha256(existing).hexdigest() != checksum:
                    raise ImmutableObjectConflict(
                        f"immutable weather-field key won a conflicting write race: {key}"
                    )
            return StoredObject(key, len(data), checksum, self.public_url(key))
        finally:
            temporary.unlink(missing_ok=True)


class S3FieldObjectStorage:
    """S3-compatible immutable storage for production field assets.

    The bucket stays private to writers; ``public_base_url`` points at the CDN or
    read-only object origin used by browsers. Conditional creation prevents two
    workers from silently replacing the same content-addressed publication key.
    """

    def __init__(
        self,
        *,
        bucket: str,
        public_base_url: str,
        client: Any,
        key_prefix: str = "",
    ):
        self.bucket = bucket.strip()
        self.public_base_url = public_base_url.rstrip("/")
        self.client = client
        self.key_prefix = key_prefix.strip("/")
        if not self.bucket:
            raise ValueError("bucket must not be empty")
        if not self.public_base_url:
            raise ValueError("public_base_url must not be empty")
        if self.key_prefix:
            validate_object_key(self.key_prefix)

    def _object_key(self, key: str) -> str:
        canonical = validate_object_key(key)
        return f"{self.key_prefix}/{canonical}" if self.key_prefix else canonical

    def public_url(self, key: str) -> str:
        canonical = validate_object_key(key)
        encoded = "/".join(quote(part, safe="-._~") for part in canonical.split("/"))
        return f"{self.public_base_url}/{encoded}"

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode") if isinstance(response, dict) else None
        return status == 404 or str(error.get("Code", "")) in {
            "404",
            "NoSuchKey",
            "NotFound",
        }

    @staticmethod
    def _is_precondition_failed(exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode") if isinstance(response, dict) else None
        return status == 412 or str(error.get("Code", "")) in {
            "412",
            "PreconditionFailed",
            "ConditionalRequestConflict",
        }

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._object_key(key))
        except Exception as exc:
            if self._is_missing(exc):
                return False
            raise
        return True

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=self._object_key(key))
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._object_key(key))

    def put_immutable(self, key: str, data: bytes) -> StoredObject:
        canonical = validate_object_key(key)
        checksum = hashlib.sha256(data).hexdigest()
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._object_key(canonical),
                Body=data,
                ContentType=_content_type(canonical),
                CacheControl="public, max-age=31536000, immutable",
                Metadata={"sha256": checksum},
                IfNoneMatch="*",
            )
        except Exception as exc:
            if not self._is_precondition_failed(exc):
                raise
            existing = self.get(canonical)
            if hashlib.sha256(existing).hexdigest() != checksum:
                raise ImmutableObjectConflict(
                    f"immutable weather-field key already exists with different content: {key}"
                ) from exc
            data = existing
        return StoredObject(
            canonical,
            len(data),
            checksum,
            self.public_url(canonical),
        )


def _content_type(key: str) -> str:
    if key.endswith(".json"):
        return "application/json"
    if key.endswith(".gz"):
        return "application/gzip"
    if key.endswith(".sws1"):
        return "application/vnd.surfwinddata.field-series"
    return "application/octet-stream"


class MemoryFieldObjectStorage:
    """Deterministic in-memory implementation for pipelines and unit tests."""

    def __init__(self, *, public_base_url: str = "https://fields.invalid"):
        self.public_base_url = public_base_url.rstrip("/")
        self._objects: dict[str, bytes] = {}

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{validate_object_key(key)}"

    def exists(self, key: str) -> bool:
        return validate_object_key(key) in self._objects

    def get(self, key: str) -> bytes:
        return self._objects[validate_object_key(key)]

    def delete(self, key: str) -> None:
        self._objects.pop(validate_object_key(key), None)

    def put_immutable(self, key: str, data: bytes) -> StoredObject:
        canonical = validate_object_key(key)
        existing = self._objects.get(canonical)
        if existing is not None and existing != data:
            raise ImmutableObjectConflict(
                f"immutable weather-field key already exists with different content: {key}"
            )
        self._objects[canonical] = bytes(data)
        return StoredObject(
            canonical,
            len(data),
            hashlib.sha256(data).hexdigest(),
            self.public_url(canonical),
        )


def configured_field_storage() -> FieldObjectStorage:
    """Build the configured local or S3-compatible field data plane."""
    from app.config import get_settings

    settings = get_settings()
    if settings.weather_field_storage_backend == "local":
        return LocalFieldObjectStorage(
            settings.weather_field_storage_dir,
            public_base_url=settings.weather_field_public_base_url,
        )
    if settings.weather_field_storage_backend == "s3":
        if not settings.weather_field_storage_bucket:
            raise RuntimeError("WEATHER_FIELD_STORAGE_BUCKET is required for s3")
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=settings.weather_field_storage_endpoint or None,
            region_name=settings.weather_field_storage_region or None,
            aws_access_key_id=settings.weather_field_storage_access_key or None,
            aws_secret_access_key=settings.weather_field_storage_secret_key or None,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.weather_field_storage_addressing_style},
            ),
        )
        return S3FieldObjectStorage(
            bucket=settings.weather_field_storage_bucket,
            key_prefix=settings.weather_field_storage_prefix,
            public_base_url=settings.weather_field_public_base_url,
            client=client,
        )
    raise RuntimeError("unsupported weather-field storage backend")
