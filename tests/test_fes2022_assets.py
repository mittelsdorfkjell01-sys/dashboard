from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from scripts.fes2022_assets import (
    CONSTITUENTS,
    MASK_ARCHIVE,
    parse_catalog,
    pyfes_config_text,
    validate_target,
    write_metadata,
)


def _catalog() -> bytes:
    datasets = []
    names = [f"{name}_fes2022.nc.xz" for name in CONSTITUENTS.values()] + [MASK_ARCHIVE]
    for name in names:
        datasets.append(
            f'<dataset name="{name}" urlPath="private/{name}">'
            '<dataSize units="Mbytes">1.5</dataSize></dataset>'
        )
    return (
        '<catalog xmlns="http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0">'
        + "".join(datasets)
        + "</catalog>"
    ).encode()


def test_catalog_requires_the_complete_extrapolated_atlas():
    entries = parse_catalog(_catalog())
    assert len(entries) == 35
    assert sum(item.size_bytes for item in entries) == 52_500_000

    with pytest.raises(ValueError, match="does not match"):
        parse_catalog(_catalog().replace(b"m2_fes2022.nc.xz", b"missing.nc.xz"))


def test_installer_refuses_repository_target(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    with pytest.raises(ValueError, match="outside the repository"):
        validate_target(repository / "private" / "fes", repository=repository)


def test_metadata_has_all_assets_and_no_credentials(tmp_path):
    target = tmp_path / "private-fes"
    atlas = target / "ocean_tide_extrapolated"
    atlas.mkdir(parents=True)
    for filename in CONSTITUENTS.values():
        (atlas / f"{filename}_fes2022.nc").write_bytes(filename.encode())
    (atlas / MASK_ARCHIVE.removesuffix(".xz")).write_bytes(b"mask")
    (target / "natural-earth-ne-10m-land.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
    )

    paths = write_metadata(target, datetime(2026, 11, 12, tzinfo=timezone.utc))
    manifest = json.loads((target / "tide-assets.json").read_text(encoding="utf-8"))
    roles = {item["role"] for item in manifest["files"]}

    assert len(manifest["files"]) == 37
    assert manifest["license_review_due_at"] == "2031-11-12T00:00:00Z"
    assert {"pyfes_config", "mask", "land_geojson"} <= roles
    assert {f"constituent:{name}" for name in CONSTITUENTS} <= roles
    assert "AVISO_PASSWORD" not in (target / "worker.env").read_text(encoding="utf-8")
    assert hashlib.sha256((target / "fes2022.yaml").read_bytes()).hexdigest() == next(
        item["sha256"] for item in manifest["files"] if item["role"] == "pyfes_config"
    )
    assert paths["worker_env"].endswith("worker.env")


def test_pyfes_config_uses_only_official_extrapolated_height_files():
    content = pyfes_config_text()
    assert "load_tide" not in content
    assert "ocean_tide_extrapolated/m2_fes2022.nc" in content
    assert content.count("_fes2022.nc") == 34
