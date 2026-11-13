from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.tides.preflight import tide_asset_preflight


def _write(path, content: bytes) -> str:
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _fixture(tmp_path, *, expired: bool = False) -> Settings:
    config = tmp_path / "fes2022.yaml"
    mask = tmp_path / "fes2022b_mask.nc"
    land = tmp_path / "natural-earth-land.geojson"
    digests = {
        "pyfes_config": _write(config, b"tide: {}\n"),
        "mask": _write(mask, b"netcdf-mask"),
        "land_geojson": _write(land, b'{"type":"FeatureCollection","features":[]}'),
    }
    now = datetime.now(timezone.utc)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "model_name": "FES2022b",
        "model_version": "2022b",
        "license_accepted_at": (now - timedelta(days=1)).isoformat(),
        "license_review_due_at": (now - timedelta(days=1) if expired else now + timedelta(days=365)).isoformat(),
        "files": [
            {"role": role, "path": path.name, "sha256": digests[role]}
            for role, path in {
                "pyfes_config": config,
                "mask": mask,
                "land_geojson": land,
            }.items()
        ],
    }), encoding="utf-8")
    return Settings(
        tide_model_dir=str(tmp_path),
        tide_pyfes_config=str(config),
        tide_mask_file=str(mask),
        tide_land_geojson=str(land),
        tide_asset_manifest=str(manifest),
    )


def test_tide_asset_preflight_verifies_manifest_and_checksums(tmp_path):
    result = tide_asset_preflight(_fixture(tmp_path), verify_checksums=True)
    assert result["ready"] is True
    assert all(check["passed"] for check in result["checks"])


def test_tide_asset_preflight_rejects_expired_licence_review(tmp_path):
    result = tide_asset_preflight(_fixture(tmp_path, expired=True), verify_checksums=True)
    assert result["ready"] is False
    failed = {check["name"] for check in result["checks"] if not check["passed"]}
    assert "manifest:license_current" in failed
