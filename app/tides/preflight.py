"""Fail-closed validation for the private FES2022b worker volume."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from app.config import Settings
from app.tides import MODEL_NAME, MODEL_VERSION

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_ROLES = {"pyfes_config", "mask", "land_geojson"}


def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def tide_asset_preflight(
    settings: Settings,
    *,
    verify_checksums: bool = False,
    load_pyfes: bool = False,
) -> dict:
    """Validate configuration, licence evidence and optional file digests.

    Model paths are reported by role and basename only, so CI logs never expose
    the private worker volume layout or AVISO credentials.
    """

    configured = {
        "model_dir": settings.tide_model_dir,
        "pyfes_config": settings.tide_pyfes_config,
        "mask": settings.tide_mask_file,
        "land_geojson": settings.tide_land_geojson,
        "manifest": settings.tide_asset_manifest,
    }
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    paths = {
        role: Path(raw).expanduser().resolve()
        for role, raw in configured.items()
        if raw
    }
    for role in configured:
        path = paths.get(role)
        expected_directory = role == "model_dir"
        exists = bool(path and (path.is_dir() if expected_directory else path.is_file()))
        add(f"path:{role}", exists, path.name if exists and path else "missing")

    model_dir = paths.get("model_dir")
    if model_dir and model_dir.is_dir():
        for role in ("pyfes_config", "mask", "land_geojson", "manifest"):
            path = paths.get(role)
            contained = bool(path and path.is_relative_to(model_dir))
            add(f"private_volume:{role}", contained, "inside model directory" if contained else "outside model directory")

    manifest: dict = {}
    manifest_path = paths.get("manifest")
    if manifest_path and manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = loaded if isinstance(loaded, dict) else {}
            add("manifest:json", bool(manifest), "valid JSON object" if manifest else "empty or invalid object")
        except (OSError, json.JSONDecodeError):
            add("manifest:json", False, "invalid JSON")

    add("manifest:model", manifest.get("model_name") == MODEL_NAME, str(manifest.get("model_name") or "missing"))
    add("manifest:version", manifest.get("model_version") == MODEL_VERSION, str(manifest.get("model_version") or "missing"))
    accepted_at = _instant(manifest.get("license_accepted_at"))
    review_due_at = _instant(manifest.get("license_review_due_at"))
    add("manifest:license_accepted", accepted_at is not None, "recorded" if accepted_at else "missing ISO timestamp")
    license_current = bool(review_due_at and review_due_at > datetime.now(timezone.utc))
    add("manifest:license_current", license_current, review_due_at.isoformat() if review_due_at else "missing ISO timestamp")

    entries = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    roles = [
        item.get("role")
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    ]
    add("manifest:unique_roles", len(roles) == len(set(roles)), f"{len(roles)} entries")
    by_role = {
        item.get("role"): item
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    }
    add("manifest:required_roles", _REQUIRED_ROLES <= set(by_role), ", ".join(sorted(set(by_role))))

    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("role"), str):
            add("manifest:file_entry", False, "invalid entry")
            continue
        role = entry["role"]
        recorded = Path(str(entry.get("path") or ""))
        file_path = recorded if recorded.is_absolute() else (model_dir / recorded if model_dir else recorded)
        try:
            resolved = file_path.expanduser().resolve()
            contained = bool(model_dir and resolved.is_relative_to(model_dir))
        except OSError:
            resolved = file_path
            contained = False
        exists = contained and resolved.is_file() and resolved.stat().st_size > 0
        digest = str(entry.get("sha256") or "").lower()
        digest_valid = bool(_SHA256.fullmatch(digest))
        add(f"file:{role}:private", contained, recorded.name or "missing")
        add(f"file:{role}:exists", exists, recorded.name or "missing")
        add(f"file:{role}:sha256", digest_valid, "recorded" if digest_valid else "missing or invalid")
        if verify_checksums and exists and digest_valid:
            add(f"checksum:{role}", _digest(resolved) == digest, recorded.name)

    for role in _REQUIRED_ROLES:
        expected_path = paths.get(role)
        entry = by_role.get(role) or {}
        recorded_name = Path(str(entry.get("path") or "")).name
        name_matches = bool(expected_path and recorded_name == expected_path.name)
        digest = str(entry.get("sha256") or "").lower()
        digest_valid = bool(_SHA256.fullmatch(digest))
        add(f"manifest:{role}:path", name_matches, recorded_name or "missing")
        add(f"manifest:{role}:sha256", digest_valid, "recorded" if digest_valid else "missing or invalid")
    if load_pyfes:
        try:
            version = metadata.version("pyfes")
            import pyfes

            config_path = paths.get("pyfes_config")
            if config_path is None:
                raise RuntimeError("configuration missing")
            configuration = pyfes.config.load(str(config_path))
            usable = "tide" in configuration.models
            add("pyfes:load", usable, f"pyfes {version}; tide model {'present' if usable else 'missing'}")
        except Exception as exc:
            add("pyfes:load", False, f"configuration load failed ({type(exc).__name__})")

    return {
        "ready": all(item["passed"] for item in checks),
        "model": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "checks": checks,
    }


def assert_tide_assets_ready(settings: Settings) -> None:
    result = tide_asset_preflight(settings, load_pyfes=True)
    failed = [item["name"] for item in result["checks"] if not item["passed"]]
    if failed:
        raise RuntimeError("Tide-Asset-Preflight fehlgeschlagen: " + ", ".join(failed))
