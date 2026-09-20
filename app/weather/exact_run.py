"""Internal, first-seen-as-of exact-run assets for LiveWind shadow evidence.

No historical publication time is inferred from a model initialization. An
asset becomes eligible only after this worker has captured and checksummed it.
The cache is a persistent, shared mount; never point it at ephemeral /tmp in
production. Public current and forecast serving do not import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
from typing import Callable

from app.forecast.contracts import ProviderRequest
from app.forecast.providers import DwdIconProvider, InvalidModelData, NoaaGfsProvider, ProviderUnavailable
from app.weather.model_error import (
    EXACT_SAMPLE_VERSION, ModelWindPoint, StationModelBaseline,
    exact_sample_identity,
)

LEGACY_EXACT_BUNDLE_VERSION = "exact-run-bundle-v1"
EXACT_BUNDLE_VERSION = "exact-run-bundle-v2"
EXACT_LOADER_VERSION = "exact-run-loader-v2"
EXACT_DATASET_MANIFEST_VERSION = "exact-run-dataset-manifest-v2"
EXPECTED_MODELS = ("gfs-0p25", "icon-eu")
CACHE_ID_FILE = ".exact-run-cache-id"
DATASET_VERSIONS = {"gfs-0p25": "GFS 0.25", "icon-eu": "DWD Open Data"}
FIELDS = {"gfs-0p25": ("10u", "10v"), "icon-eu": ("u_10m", "v_10m")}
STATUS = {
    "available", "provider_unavailable", "run_not_available_as_of_observation",
    "availability_unproven", "missing_time_bracket", "cross_run_interpolation_rejected",
    "dataset_version_mismatch", "checksum_mismatch", "cache_incomplete",
    "sampling_failed", "not_activation_eligible", "legacy_capture_time_baseline",
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("exact-run times must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _complete_grib(data: bytes) -> bytes:
    """Reject HTML, empty and visibly truncated upstream responses before publication."""
    if not data.startswith(b"GRIB") or not data.endswith(b"7777"):
        raise ExactAssetError("cache_incomplete")
    return data


def gfs_tile(lat: float, lon: float) -> tuple[float, float, float, float]:
    """Stable ten-degree request tile; logical bundle identity is tile-independent."""
    south = max(-90, min(80, math.floor(lat / 10) * 10))
    west = math.floor((lon % 360) / 10) * 10
    return (float(west), float(west + 10), float(south), float(south + 10))


def _domain(model: str, lat: float, lon: float) -> str:
    if model == "icon-eu":
        return "icon-eu-full-grid"
    return "gfs-tile:" + ",".join(f"{value:g}" for value in gfs_tile(lat, lon))


def _asset_available_as_of(asset: "ExactAsset", as_of: datetime) -> bool:
    """Only a completed pre-observation capture proves availability today."""
    return (
        asset.availability_basis == "first_seen_capture"
        and asset.first_seen_at is not None
        and asset.retrieval_completed_at is not None
        and (asset.retrieval_started_at is None
             or asset.retrieval_started_at <= asset.retrieval_completed_at)
        and asset.retrieval_completed_at <= asset.first_seen_at <= as_of
        and asset.available_at == asset.first_seen_at
    )


def compatible_dataset_manifests(left: dict | None, right: dict | None) -> bool:
    """Explicit semantic check in addition to a matching dataset hash."""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    required = ("schema_version", "loader_version", "required_models",
                "eligibility_class", "availability_basis", "members")
    if any(key not in left or key not in right for key in required):
        return False
    if any(value.get("schema_version") != EXACT_DATASET_MANIFEST_VERSION
           or value.get("loader_version") != EXACT_LOADER_VERSION
           or not isinstance(value.get("members"), dict)
           for value in (left, right)):
        return False
    if left["eligibility_class"] != "captured_before_observation":
        return False
    if right["eligibility_class"] != "captured_before_observation":
        return False
    if left["availability_basis"] != "first_seen_capture":
        return False
    if right["availability_basis"] != "first_seen_capture":
        return False
    if tuple(left["required_models"]) != EXPECTED_MODELS:
        return False
    if tuple(right["required_models"]) != EXPECTED_MODELS:
        return False
    for model in EXPECTED_MODELS:
        a, b = left["members"].get(model), right["members"].get(model)
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        for key in ("provider", "model", "run_at", "dataset_version",
                    "valid_times", "forecast_leads_hours", "required_fields",
                    "source_objects", "source_revision"):
            if a.get(key) != b.get(key):
                return False
    return all(left[key] == right[key] for key in required)


@dataclass(frozen=True)
class ExactAsset:
    key: str
    provider: str
    model: str
    run_at: datetime
    valid_at: datetime
    lead_hours: int
    dataset_version: str
    field: str
    domain: str
    grid_definition: str
    source_id: str
    content_sha256: str
    available_at: datetime
    fetched_at: datetime
    bytes: int
    cache_hit: bool = False
    provider_published_at: datetime | None = None
    first_seen_at: datetime | None = None
    retrieval_started_at: datetime | None = None
    retrieval_completed_at: datetime | None = None
    availability_basis: str = "first_seen_capture"

    @property
    def asset_content_hash(self) -> str:
        return _hash({
            "provider": self.provider, "model": self.model,
            "run_at": self.run_at.isoformat(), "valid_at": self.valid_at.isoformat(),
            "dataset_version": self.dataset_version, "field": self.field,
            "domain": self.domain, "grid_definition": self.grid_definition,
            "source_id": self.source_id, "content_sha256": self.content_sha256,
        })

    def manifest(self) -> dict:
        payload = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in self.__dict__.items() if key != "cache_hit"
        }
        payload["asset_content_hash"] = self.asset_content_hash
        return payload

    @classmethod
    def from_manifest(cls, value: dict, *, cache_hit: bool = True) -> "ExactAsset":
        fields = dict(value)
        claimed_hash = fields.pop("asset_content_hash", None)
        # A v1 cache manifest only recorded a capture-time `available_at`.
        # It cannot be upgraded into proof of completed pre-observation capture.
        if any(name not in fields for name in (
            "first_seen_at", "retrieval_completed_at", "availability_basis"
        )):
            fields["first_seen_at"] = None
            fields["retrieval_completed_at"] = None
            fields["availability_basis"] = "availability_unproven"
        asset = cls(**{
            **fields,
            "run_at": _utc(datetime.fromisoformat(value["run_at"])),
            "valid_at": _utc(datetime.fromisoformat(value["valid_at"])),
            "available_at": _utc(datetime.fromisoformat(value["available_at"])),
            "fetched_at": _utc(datetime.fromisoformat(value["fetched_at"])),
            **{
                name: _utc(datetime.fromisoformat(fields[name])) if fields.get(name) else None
                for name in ("provider_published_at", "first_seen_at",
                             "retrieval_started_at", "retrieval_completed_at")
            },
            "cache_hit": cache_hit,
        })
        if claimed_hash is not None and claimed_hash != asset.asset_content_hash:
            raise ExactAssetError("checksum_mismatch")
        return asset


class ExactAssetError(RuntimeError):
    def __init__(self, status: str):
        if status not in STATUS:
            raise ValueError(status)
        super().__init__(status)
        self.status = status


def exact_cache_preflight(
    root: str | Path, *, expected_id: str | None = None,
    require_persistent: bool = False, minimum_free_bytes: int = 0,
) -> dict:
    """Check shared-cache identity, durability prerequisites and atomic rename."""
    supplied = Path(root)
    if not supplied.is_absolute() or not supplied.is_dir():
        raise ValueError("exact_run_cache_missing_or_not_absolute")
    resolved = supplied.resolve()
    if supplied != resolved or supplied.is_symlink():
        raise ValueError("exact_run_cache_symlink_or_redirected")
    if require_persistent:
        if os.name != "posix" or not os.path.ismount(resolved):
            raise ValueError("exact_run_cache_not_a_linux_mount")
        mount_lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        match = next((line for line in mount_lines
                      if len(line.split()) > 4 and line.split()[4] == str(resolved)), None)
        if match is None or " - " not in match:
            raise ValueError("exact_run_cache_mount_unverified")
        filesystem = match.split(" - ", 1)[1].split()[0]
        if filesystem in {"overlay", "tmpfs", "ramfs", "squashfs"}:
            raise ValueError("exact_run_cache_ephemeral_filesystem")
        if not expected_id:
            raise ValueError("exact_run_cache_expected_id_missing")
        if resolved.stat().st_mode & 0o002:
            raise ValueError("exact_run_cache_world_writable")
    marker = resolved / CACHE_ID_FILE
    if require_persistent and marker.is_symlink():
        raise ValueError("exact_run_cache_identity_symlink")
    cache_id = marker.read_text(encoding="utf-8").strip() if marker.is_file() else None
    if require_persistent and (not cache_id or cache_id != expected_id):
        raise ValueError("exact_run_cache_identity_mismatch")
    free_bytes = shutil.disk_usage(resolved).free
    if free_bytes < minimum_free_bytes:
        raise ValueError("exact_run_cache_low_disk_space")
    probe = resolved / f".exact-run-preflight-{os.getpid()}-{time.monotonic_ns()}"
    renamed = probe.with_suffix(".renamed")
    try:
        probe.write_bytes(b"atomic-probe")
        os.replace(probe, renamed)
        if renamed.read_bytes() != b"atomic-probe":
            raise ValueError("exact_run_cache_atomic_rename_failed")
    finally:
        probe.unlink(missing_ok=True)
        renamed.unlink(missing_ok=True)
    return {
        "cache_dir": str(resolved), "cache_id": cache_id,
        "persistent_mount_verified": require_persistent,
        "free_bytes": free_bytes,
        "manifest_version": EXACT_DATASET_MANIFEST_VERSION,
    }


class ExactRunAssetCache:
    """Immutable CAS objects with atomic manifests and cross-process lock files."""

    def __init__(self, root: str | Path, *, require_persistent: bool = False,
                 expected_id: str | None = None, minimum_free_bytes: int = 0):
        if require_persistent:
            exact_cache_preflight(root, expected_id=expected_id,
                                  require_persistent=True,
                                  minimum_free_bytes=minimum_free_bytes)
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def asset_key(*, model: str, run_at: datetime, valid_at: datetime,
                  dataset_version: str, field: str, domain: str) -> str:
        return _hash({"model": model, "run_at": _utc(run_at).isoformat(),
                      "valid_at": _utc(valid_at).isoformat(), "dataset_version": dataset_version,
                      "field": field, "domain": domain})

    def _manifest_path(self, key: str) -> Path:
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("invalid exact-run asset key")
        return self.root / "manifests" / key[:2] / f"{key}.json"

    def _object_path(self, digest: str) -> Path:
        return self.root / "objects" / digest[:2] / digest

    def _conflict_path(self, key: str) -> Path:
        self._manifest_path(key)  # validate the key
        return self.root / "conflicts" / key[:2] / f"{key}.json"

    def conflicted(self, key: str) -> bool:
        return self._conflict_path(key).exists()

    def read(self, key: str) -> tuple[ExactAsset, bytes] | None:
        path = self._manifest_path(key)
        if not path.exists():
            return None
        try:
            asset = ExactAsset.from_manifest(json.loads(path.read_text(encoding="utf-8")))
            if asset.key != key:
                raise ExactAssetError("cache_incomplete")
            data = self._object_path(asset.content_sha256).read_bytes()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ExactAssetError("cache_incomplete") from exc
        if len(data) != asset.bytes or hashlib.sha256(data).hexdigest() != asset.content_sha256:
            raise ExactAssetError("checksum_mismatch")
        return asset, data

    def capture(self, *, model: str, run_at: datetime, valid_at: datetime,
                field: str, domain: str, source_id: str, provider: str,
                grid_definition: str, downloader: Callable[[], bytes],
                now: datetime | None = None, refresh: bool = False) -> ExactAsset:
        run_at, valid_at = _utc(run_at), _utc(valid_at)
        dataset_version = DATASET_VERSIONS[model]
        key = self.asset_key(model=model, run_at=run_at, valid_at=valid_at,
                             dataset_version=dataset_version, field=field, domain=domain)
        path = self._manifest_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = path.with_suffix(".lock")
        deadline = time.monotonic() + 20.0
        lock_handle = None
        if os.name == "posix":
            import fcntl

            # An advisory lock survives as a path but is released by the OS
            # when a killed worker exits; never unlink a flock lock inode.
            lock_handle = lock.open("a+b")
            try:
                while True:
                    try:
                        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise ExactAssetError("cache_incomplete")
                        time.sleep(0.05)
            except Exception:
                lock_handle.close()
                raise
        else:
            while True:
                try:
                    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(fd)
                    break
                except FileExistsError:
                    if time.monotonic() >= deadline:
                        raise ExactAssetError("cache_incomplete")
                    time.sleep(0.05)
        try:
            previous = self.read(key)
            if previous is not None and not refresh:
                return previous[0]
            retrieval_started_at = _utc(now) if now is not None else datetime.now(timezone.utc)
            data = downloader()
            retrieval_completed_at = _utc(now) if now is not None else datetime.now(timezone.utc)
            if not data:
                raise ExactAssetError("cache_incomplete")
            digest = hashlib.sha256(data).hexdigest()
            if previous is not None:
                if previous[0].source_id != source_id or previous[0].content_sha256 != digest:
                    conflict = self._conflict_path(key)
                    conflict.parent.mkdir(parents=True, exist_ok=True)
                    temporary_conflict = conflict.with_name(f"{key}.part-{os.getpid()}-{time.monotonic_ns()}")
                    try:
                        temporary_conflict.write_text(json.dumps({
                            "key": key, "previous_sha256": previous[0].content_sha256,
                            "new_sha256": digest, "previous_source_id": previous[0].source_id,
                            "new_source_id": source_id,
                            "detected_at": datetime.now(timezone.utc).isoformat(),
                        }, sort_keys=True), encoding="utf-8")
                        os.replace(temporary_conflict, conflict)
                    finally:
                        temporary_conflict.unlink(missing_ok=True)
                    raise ExactAssetError("checksum_mismatch")
                return previous[0]
            object_path = self._object_path(digest)
            object_path.parent.mkdir(parents=True, exist_ok=True)
            if not object_path.exists():
                temporary = object_path.with_name(f"{digest}.part-{os.getpid()}-{time.monotonic_ns()}")
                try:
                    temporary.write_bytes(data)
                    if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
                        raise ExactAssetError("checksum_mismatch")
                    os.replace(temporary, object_path)
                finally:
                    temporary.unlink(missing_ok=True)
            # First-seen is recorded only after the complete object is durable.
            # Never time-stamp an in-progress download as available.
            captured_at = _utc(now or datetime.now(timezone.utc))
            asset = ExactAsset(
                key=key, provider=provider, model=model, run_at=run_at, valid_at=valid_at,
                lead_hours=int((valid_at-run_at).total_seconds() // 3600),
                dataset_version=dataset_version, field=field, domain=domain,
                grid_definition=grid_definition, source_id=source_id,
                content_sha256=digest, available_at=captured_at, fetched_at=captured_at,
                bytes=len(data),
                first_seen_at=captured_at,
                retrieval_started_at=retrieval_started_at,
                retrieval_completed_at=retrieval_completed_at,
            )
            temporary_manifest = path.with_name(f"{key}.part-{os.getpid()}-{time.monotonic_ns()}")
            try:
                temporary_manifest.write_text(json.dumps(asset.manifest(), sort_keys=True), encoding="utf-8")
                os.replace(temporary_manifest, path)
            finally:
                temporary_manifest.unlink(missing_ok=True)
            return asset
        finally:
            if lock_handle is not None:
                import fcntl
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                lock_handle.close()
            else:
                lock.unlink(missing_ok=True)

    def inventory(self) -> tuple[ExactAsset, ...]:
        """Return every readable immutable asset, ignoring broken manifests."""
        result = []
        root = self.root / "manifests"
        if not root.exists():
            return ()
        for path in root.glob("*/*.json"):
            try:
                item = ExactAsset.from_manifest(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError, TypeError, ExactAssetError):
                continue
            result.append(item)
        return tuple(sorted(result, key=lambda item: (item.run_at, item.valid_at, item.field, item.key)))

    def assets(self, *, model: str, domain: str) -> tuple[ExactAsset, ...]:
        return tuple(
            item for item in self.inventory()
            if item.model == model and item.domain == domain
        )


@dataclass(frozen=True)
class BaselineBundle:
    bundle_hash: str
    dataset_bundle_hash: str
    dataset_manifest: dict
    version: str
    loader_version: str
    valid_at: datetime
    members: dict[str, dict]
    statuses: dict[str, str]
    activation_eligible: bool

    def manifest(self) -> dict:
        return {"bundle_hash": self.bundle_hash,
                "dataset_bundle_hash": self.dataset_bundle_hash,
                "dataset_manifest": json.loads(json.dumps(self.dataset_manifest)),
                "version": self.version,
                "loader_version": self.loader_version, "valid_at": self.valid_at.isoformat(),
                "members": json.loads(json.dumps(self.members)), "statuses": dict(self.statuses),
                "activation_eligible": self.activation_eligible}


class ExactRunLoader:
    """Shared station/target sampler; cache-only lookup never fetches history."""

    def __init__(self, cache: ExactRunAssetCache, *, gfs: NoaaGfsProvider | None = None,
                 icon: DwdIconProvider | None = None):
        self.cache = cache
        self.gfs = gfs or NoaaGfsProvider()
        self.icon = icon or DwdIconProvider()

    def capture(self, *, run_at: datetime, forecast_hours: tuple[int, ...],
                latitude: float, longitude: float, now: datetime | None = None,
                verify_existing: bool = False) -> dict:
        """Pre-capture only official raw wind fields for one reusable GFS tile."""
        run_at = _utc(run_at)
        report = {"assets": 0, "cache_hits": 0, "cache_misses": 0,
                  "errors": {}, "model_runs": {}, "provider_duration_ms": {}}
        for model in EXPECTED_MODELS:
            model_started = time.monotonic()
            domain = _domain(model, latitude, longitude)
            report["model_runs"][model] = run_at.isoformat()
            for hour in forecast_hours:
                valid_at = run_at + timedelta(hours=hour)
                if model == "gfs-0p25":
                    source_id, _ = self.gfs.subset_source(run_at, hour, gfs_tile(latitude, longitude))
                    fields = ("10m_wind_uv",)
                else:
                    fields = FIELDS[model]
                for field in fields:
                    source = source_id if model == "gfs-0p25" else self.icon.file_url(model, run_at, field, hour)
                    try:
                        asset = self.cache.capture(
                            model=model, run_at=run_at, valid_at=valid_at, field=field,
                            domain=domain, source_id=source,
                            provider="NOAA/NCEP" if model == "gfs-0p25" else "Deutscher Wetterdienst",
                            grid_definition="GFS 0.25 regular lat/lon" if model == "gfs-0p25" else "ICON-EU regular lat/lon",
                            downloader=(
                                (lambda h=hour: _complete_grib(
                                    self.gfs.download_subset(run_at, h, gfs_tile(latitude, longitude))[1]))
                                if model == "gfs-0p25" else
                                (lambda url=source: _complete_grib(self.icon.download(url)))
                            ),
                            now=now,
                            refresh=verify_existing,
                        )
                        report["assets"] += 1
                        report["cache_hits"] += int(asset.cache_hit)
                        report["cache_misses"] += int(not asset.cache_hit)
                    except Exception as exc:
                        reason = (
                            exc.status if isinstance(exc, ExactAssetError)
                            else "provider_unavailable" if isinstance(exc, ProviderUnavailable)
                            else "cache_incomplete" if isinstance(exc, InvalidModelData)
                            else "sampling_failed"
                        )
                        report["errors"].setdefault(model, []).append({
                            "lead": hour, "field": field, "status": reason,
                            "error_class": type(exc).__name__,
                        })
            report["provider_duration_ms"][model] = round((time.monotonic()-model_started)*1000)
        return report

    def bundle(self, *, valid_at: datetime, latitude: float, longitude: float,
               as_of: datetime | None = None) -> BaselineBundle:
        valid_at = _utc(valid_at)
        as_of = _utc(as_of or valid_at)
        members, statuses = {}, {}
        for model in EXPECTED_MODELS:
            domain = _domain(model, latitude, longitude)
            items = self.cache.assets(model=model, domain=domain)
            groups: dict[datetime, dict[datetime, dict[str, ExactAsset]]] = {}
            for item in items:
                groups.setdefault(item.run_at, {}).setdefault(item.valid_at, {})[item.field] = item
            candidates = []
            for run_at, times in groups.items():
                if run_at >= valid_at:
                    continue
                lower = max((t for t in times if t <= valid_at), default=None)
                upper = min((t for t in times if t >= valid_at), default=None)
                if lower is None or upper is None:
                    continue
                selected = [times[t][field] for t in dict.fromkeys((lower, upper))
                            for field in (("10m_wind_uv",) if model == "gfs-0p25" else FIELDS[model])
                            if field in times[t]]
                expected = len(tuple(dict.fromkeys((lower, upper)))) * (1 if model == "gfs-0p25" else 2)
                if len(selected) != expected:
                    continue
                if any(self.cache.conflicted(item.key) for item in selected):
                    statuses[model] = "checksum_mismatch"
                    continue
                if any(item.dataset_version != DATASET_VERSIONS[model] for item in selected):
                    statuses[model] = "dataset_version_mismatch"
                    continue
                if all(_asset_available_as_of(item, as_of) for item in selected):
                    candidates.append((run_at, lower, upper, selected))
            if not candidates:
                if model not in statuses:
                    has_lower = any(item.valid_at < valid_at for item in items)
                    has_upper = any(item.valid_at > valid_at for item in items)
                    statuses[model] = (
                        "run_not_available_as_of_observation"
                        if any(not _asset_available_as_of(item, as_of) for item in items)
                        else "cross_run_interpolation_rejected" if has_lower and has_upper
                        else "missing_time_bracket" if items else "availability_unproven"
                    )
                continue
            run_at, lower, upper, selected = max(candidates, key=lambda value: value[0])
            members[model] = {
                "run_at": run_at.isoformat(), "run_id": f"{model}:{run_at.isoformat()}",
                "dataset_version": DATASET_VERSIONS[model], "domain": domain,
                "valid_times": [t.isoformat() for t in dict.fromkeys((lower, upper))],
                "assets": [item.manifest() for item in sorted(selected, key=lambda asset: (asset.valid_at, asset.field))],
            }
            statuses[model] = "available"
        identity = {"version": EXACT_BUNDLE_VERSION, "loader": EXACT_LOADER_VERSION,
                    "members": members, "statuses": statuses}
        activation_eligible = all(statuses.get(model) == "available" for model in EXPECTED_MODELS)
        dataset_members = {}
        for model, member in sorted(members.items()):
            assets = [ExactAsset.from_manifest(item) for item in member["assets"]]
            dataset_members[model] = {
                "provider": assets[0].provider,
                "model": model,
                "run_at": member["run_at"],
                "dataset_version": member["dataset_version"],
                "valid_times": sorted(member["valid_times"]),
                "forecast_leads_hours": sorted({asset.lead_hours for asset in assets}),
                "required_fields": list(FIELDS[model]),
                # Logical source objects are deliberately independent of a GFS
                # subset URL, tile, concrete grid cell and download order.
                "source_objects": sorted({
                    f"{model}:{asset.run_at.isoformat()}:f{asset.lead_hours:03d}:{asset.field}"
                    for asset in assets
                }),
                "source_revision": None,  # Neither adapter supplies a trusted revision ID.
            }
        dataset_manifest = {
            "schema_version": EXACT_DATASET_MANIFEST_VERSION,
            "loader_version": EXACT_LOADER_VERSION,
            "required_models": list(EXPECTED_MODELS),
            "eligibility_class": (
                "captured_before_observation" if activation_eligible else "availability_unproven"
            ),
            "availability_basis": "first_seen_capture",
            "members": dataset_members,
        }
        return BaselineBundle(
            bundle_hash=_hash(identity),
            dataset_bundle_hash=_hash(dataset_manifest),
            dataset_manifest=dataset_manifest,
            version=EXACT_BUNDLE_VERSION,
            loader_version=EXACT_LOADER_VERSION, valid_at=valid_at,
            members=members, statuses=statuses,
            activation_eligible=activation_eligible,
        )

    def sample(self, bundle: BaselineBundle, *, latitude: float, longitude: float) -> StationModelBaseline:
        identity = {"version": bundle.version, "loader": bundle.loader_version,
                    "members": bundle.members, "statuses": bundle.statuses}
        if (_hash(identity) != bundle.bundle_hash
                or _hash(bundle.dataset_manifest) != bundle.dataset_bundle_hash):
            return StationModelBaseline(
                points=(), expected_model_ids=EXPECTED_MODELS,
                baseline_version=EXACT_BUNDLE_VERSION,
                bundle_hash=bundle.bundle_hash, bundle_manifest=bundle.manifest(),
                dataset_bundle_hash=bundle.dataset_bundle_hash,
                dataset_manifest=bundle.dataset_manifest,
                activation_eligible=False,
                member_statuses={model: "checksum_mismatch" for model in EXPECTED_MODELS},
            )
        points = []
        statuses = dict(bundle.statuses)
        for model, member in bundle.members.items():
            if member["domain"] != _domain(model, latitude, longitude):
                statuses[model] = "sampling_failed"
                continue
            for value in member["assets"]:
                asset = ExactAsset.from_manifest(value)
                try:
                    stored = self.cache.read(asset.key)
                    if stored is None or stored[0].content_sha256 != asset.content_sha256:
                        raise ExactAssetError("checksum_mismatch")
                    _, data = stored
                    request = ProviderRequest(
                        latitude=latitude, longitude=longitude, model=model,
                        run_at=asset.run_at, forecast_hours=(asset.lead_hours,),
                    )
                    if model == "gfs-0p25":
                        sampled = self.gfs.parse_grib(data, request, asset.lead_hours)
                        u, v = sampled.u_ms, sampled.v_ms
                        grid = sampled.grid_point
                        samples = {"u": {"source_cell": [grid.latitude, grid.longitude], "weight": 1.0},
                                   "v": {"source_cell": [grid.latitude, grid.longitude], "weight": 1.0}}
                    else:
                        scalar, glat, glon = self.icon.nearest_exact_grid(data, latitude, longitude)
                        u = scalar if asset.field == "u_10m" else None
                        v = scalar if asset.field == "v_10m" else None
                        grid = (glat, glon)
                        samples = {asset.field: {"source_cell": [glat, glon], "weight": 1.0}}
                    points.append((asset, u, v, grid, samples))
                except ExactAssetError as exc:
                    statuses[model] = exc.status
                except Exception:
                    statuses[model] = "sampling_failed"
        by_model_time = {}
        for asset, u, v, grid, samples in points:
            group = by_model_time.setdefault((asset.model, asset.valid_at), [])
            group.append((asset, u, v, grid, samples))
        model_points = []
        for (model, valid_at), group in by_model_time.items():
            if statuses.get(model) != "available":
                continue
            if model == "gfs-0p25":
                asset, u, v, grid, samples = group[0]
                assets = [asset]
            else:
                if len(group) != 2 or group[0][3] != group[1][3]:
                    statuses[model] = "sampling_failed"
                    continue
                assets = [item[0] for item in group]
                u = next((item[1] for item in group if item[1] is not None), None)
                v = next((item[2] for item in group if item[2] is not None), None)
                grid = group[0][3]
                samples = {key: value for item in group for key, value in item[4].items()}
            if u is None or v is None:
                statuses[model] = "sampling_failed"
                continue
            glat, glon = (grid.latitude, grid.longitude) if model == "gfs-0p25" else grid
            lon_delta = ((glon - longitude + 180) % 360) - 180
            distance = math.hypot((glat-latitude)*111, lon_delta*111*math.cos(math.radians(latitude)))
            normalized_lon = ((glon + 180) % 360) - 180
            asset_content_hashes = tuple(sorted(item.asset_content_hash for item in assets))
            sample_manifest = {
                "sampling_version": EXACT_SAMPLE_VERSION,
                "dataset_bundle_hash": bundle.dataset_bundle_hash,
                "asset_content_hashes": list(asset_content_hashes),
                "coordinate": {"latitude": float(latitude), "longitude": float(longitude)},
                "valid_at": valid_at.isoformat(),
                "model": model,
                "sampling_method": "nearest_grid",
                "source_cells": samples,
                "u_ms": round(float(u), 9), "v_ms": round(float(v), 9),
            }
            model_points.append(ModelWindPoint(
                baseline_version=EXACT_BUNDLE_VERSION, provider=assets[0].provider,
                model_id=model, dataset_version=assets[0].dataset_version,
                model_run_id=f"{model}:{assets[0].run_at.isoformat()}", model_run_at=assets[0].run_at,
                model_run_quality="exact", valid_at=valid_at, fetched_at=assets[0].fetched_at,
                available_at=max(item.available_at for item in assets),
                latitude=glat, longitude=normalized_lon, grid_distance_km=distance,
                u_ms=float(u), v_ms=float(v), source_key=assets[0].source_id,
                asset_hashes=tuple(sorted(item.content_sha256 for item in assets)),
                asset_content_hashes=asset_content_hashes,
                sample_hash=_hash(sample_manifest), sampling_version=EXACT_SAMPLE_VERSION,
                sampling_method="nearest_grid", source_cells=samples,
                grid_definition=assets[0].grid_definition, model_height_m=10.0,
            ))
        return StationModelBaseline(
            points=tuple(sorted(model_points, key=lambda item: (item.model_id, item.valid_at))),
            expected_model_ids=EXPECTED_MODELS, baseline_version=EXACT_BUNDLE_VERSION,
            bundle_hash=bundle.bundle_hash, bundle_manifest=bundle.manifest(),
            dataset_bundle_hash=bundle.dataset_bundle_hash,
            dataset_manifest=bundle.dataset_manifest,
            activation_eligible=bundle.activation_eligible and all(statuses.get(model) == "available" for model in EXPECTED_MODELS),
            member_statuses=statuses,
        )

    def __call__(self, station, observation) -> StationModelBaseline:
        # Never fetch here: an import received after observed_at must not create
        # retroactive availability evidence.
        observed_at = _utc(observation.observed_at)
        lat = float(station.latitude)
        lon = float(station.longitude)
        bundle = self.bundle(valid_at=observed_at, latitude=lat, longitude=lon, as_of=observed_at)
        return self.sample(bundle, latitude=lat, longitude=lon)


def exact_shadow_baseline(loader: ExactRunLoader, spot, *, at: datetime) -> tuple[dict, BaselineBundle]:
    """Create only an internal LiveWind target from the same raw bundle contract."""
    from app.live.live_wind import compose_live_wind
    from app.live.service import _spot_coords
    from app.live.weather_contract import unavailable_live_wind
    from app.weather.catalog import family_for
    from app.weather.live_wind_analysis import TargetModelState, analyze_regional_live_wind
    from app.weather.model_error import DEFAULT_MODEL_ERROR_POLICY, _interpolate_member
    from app.weather.profiles import resolve_weather_profile
    from app.weather.weights import normalized_model_weights

    instant = _utc(at)
    latitude, longitude = _spot_coords(spot)
    bundle = loader.bundle(valid_at=instant, latitude=latitude, longitude=longitude, as_of=instant)
    sampled = loader.sample(bundle, latitude=latitude, longitude=longitude)
    if not sampled.activation_eligible:
        reason = next((status for status in sampled.member_statuses.values() if status != "available"),
                      "not_activation_eligible")
        return unavailable_live_wind(reason), bundle
    members = {}
    for model in EXPECTED_MODELS:
        member, error = _interpolate_member(
            [point for point in sampled.points if point.model_id == model],
            instant, policy=DEFAULT_MODEL_ERROR_POLICY,
        )
        if member is None:
            return unavailable_live_wind(error or "missing_time_bracket"), bundle
        members[model] = member
    sample_hash, sample_manifest = exact_sample_identity(
        sampled, list(members.values()),
        latitude=latitude, longitude=longitude, valid_at=instant,
    )
    lead = max((instant-member.model_run_at).total_seconds()/3600 for member in members.values())
    weights = normalized_model_weights(
        ((model, family_for(model)) for model in members), lead,
    )
    u_ms = sum(member.u_ms*weights[model] for model, member in members.items())
    v_ms = sum(member.v_ms*weights[model] for model, member in members.items())
    spread = math.sqrt(sum(
        weights[model]*((member.u_ms-u_ms)**2+(member.v_ms-v_ms)**2)
        for model, member in members.items()
    ))
    profile_row = getattr(spot, "weather_profile", None)
    profile = resolve_weather_profile(profile_row)
    target = TargetModelState(
        u_ms=u_ms, v_ms=v_ms, valid_at=instant,
        model_version=f"exact-run:{bundle.dataset_bundle_hash[:16]}",
        model_ids=tuple(members), model_spread_ms=spread,
        profile_available=profile is not None,
        terrain_complexity=float(getattr(profile, "terrain_complexity", 0.0)),
    )
    regional = analyze_regional_live_wind(target, (), analyzed_at=instant)
    captured_at = max(
        ExactAsset.from_manifest(asset).available_at
        for member in bundle.members.values() for asset in member["assets"]
    )
    baseline = compose_live_wind(
        target, regional, profile=profile,
        physics_version=getattr(profile_row, "physics_version", None),
        captured_at=captured_at,
        model_source={
            "source_type": "model_nowcast", "source": "exact_run_bundle",
            "provider": "NOAA/NCEP + Deutscher Wetterdienst",
            "model_version": target.model_version,
            "valid_at": instant, "captured_at": captured_at,
        },
    )
    baseline["_exact_bundle_hash"] = bundle.bundle_hash
    baseline["_exact_bundle_manifest"] = bundle.manifest()
    baseline["_exact_dataset_bundle_hash"] = bundle.dataset_bundle_hash
    baseline["_exact_dataset_manifest"] = bundle.dataset_manifest
    baseline["_exact_sample_hash"] = sample_hash
    baseline["_exact_sample_manifest"] = sample_manifest
    baseline["_exact_model_source"] = baseline["sources"][0]
    baseline["_model_ids"] = list(members)
    return baseline, bundle
