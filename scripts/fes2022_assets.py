"""Install the licensed AVISO FES2022b atlas on a private worker volume.

Credentials are accepted only through ``AVISO_USERNAME`` and
``AVISO_PASSWORD``.  They are never written to disk or included in output.
The installer intentionally refuses a target inside this repository because
the AVISO source files must not enter git, Vercel or a public blob store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx


CATALOG_URL = (
    "https://tds-odatis.aviso.altimetry.fr/thredds/catalog/"
    "dataset-auxiliary-fes-tide-model/fes2022b/"
    "ocean_tide_extrapolated/catalog.xml"
)
FILE_SERVER_BASE = "https://tds-odatis.aviso.altimetry.fr/thredds/fileServer/"
LAND_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_land.geojson"
)
SOURCE_URL = (
    "https://www.aviso.altimetry.fr/en/data/products/auxiliary-products/"
    "global-tide-fes.html"
)
USER_AGENT = "surfwinddata-fes-installer/1.0 (https://surfwinddata.com)"
MASK_ARCHIVE = "mask_fes2022B.nc.xz"
CONSTITUENTS = {
    "2N2": "2n2",
    "Eps2": "eps2",
    "J1": "j1",
    "K1": "k1",
    "K2": "k2",
    "L2": "l2",
    "Lambda2": "lambda2",
    "M2": "m2",
    "M3": "m3",
    "M4": "m4",
    "M6": "m6",
    "M8": "m8",
    "MKS2": "mks2",
    "MN4": "mn4",
    "MS4": "ms4",
    "MSf": "msf",
    "Mf": "mf",
    "Mm": "mm",
    "Msqm": "msqm",
    "Mtm": "mtm",
    "Mu2": "mu2",
    "N2": "n2",
    "N4": "n4",
    "Nu2": "nu2",
    "O1": "o1",
    "P1": "p1",
    "Q1": "q1",
    "R2": "r2",
    "S1": "s1",
    "S2": "s2",
    "S4": "s4",
    "Sa": "sa",
    "Ssa": "ssa",
    "T2": "t2",
}


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    url_path: str
    size_bytes: int


def _json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("license date must be ISO-8601, for example 2026-11-12") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if parsed > datetime.now(timezone.utc):
        raise ValueError("license acceptance date cannot be in the future")
    return parsed


def _review_due(accepted: datetime) -> datetime:
    try:
        return accepted.replace(year=accepted.year + 5)
    except ValueError:  # 29 February
        return accepted.replace(year=accepted.year + 5, day=28)


def validate_target(target: Path, repository: Path | None = None) -> Path:
    resolved = target.expanduser().resolve()
    repo = (repository or Path(__file__).resolve().parents[1]).resolve()
    if resolved == repo or resolved.is_relative_to(repo):
        raise ValueError("licensed FES files must be installed outside the repository")
    if resolved == Path(resolved.anchor):
        raise ValueError("target must not be a filesystem root")
    return resolved


def parse_catalog(content: bytes) -> list[CatalogEntry]:
    root = ET.fromstring(content)
    namespace = {"t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0"}
    entries: list[CatalogEntry] = []
    for node in root.findall(".//t:dataset[@urlPath]", namespace):
        name = node.attrib.get("name", "")
        url_path = node.attrib.get("urlPath", "")
        size = node.find("t:dataSize", namespace)
        if not name.endswith(".nc.xz") or not url_path or size is None or not size.text:
            continue
        unit = size.attrib.get("units", "bytes").lower()
        multiplier = {"bytes": 1, "kbytes": 1_000, "mbytes": 1_000_000}.get(unit)
        if multiplier is None:
            raise ValueError(f"unsupported AVISO catalogue size unit: {unit}")
        entries.append(CatalogEntry(name, url_path, int(float(size.text) * multiplier)))

    expected = {f"{name}_fes2022.nc.xz" for name in CONSTITUENTS.values()} | {MASK_ARCHIVE}
    found = {entry.name for entry in entries}
    if found != expected:
        missing = sorted(expected - found)
        unexpected = sorted(found - expected)
        raise ValueError(
            f"AVISO catalogue does not match FES2022b: missing={missing}, unexpected={unexpected}"
        )
    return sorted(entries, key=lambda item: item.name)


def _credentials() -> tuple[str, str]:
    username = os.environ.get("AVISO_USERNAME", "").strip()
    password = os.environ.get("AVISO_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("AVISO_USERNAME and AVISO_PASSWORD must be set in the process environment")
    return username, password


def _client(*, authenticated: bool) -> httpx.Client:
    auth = httpx.BasicAuth(*_credentials()) if authenticated else None
    return httpx.Client(
        auth=auth,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=httpx.Timeout(120.0, connect=20.0),
    )


def check_access() -> dict:
    url = f"{FILE_SERVER_BASE}dataset-auxiliary-fes-tide-model/fes2022b/ocean_tide_extrapolated/{MASK_ARCHIVE}"
    try:
        with _client(authenticated=True) as client, client.stream(
            "GET", url, headers={"Range": "bytes=0-0"}
        ) as response:
            if response.status_code == 401:
                return {
                    "ready": False,
                    "reason": "credentials rejected or FES is not enabled under My AVISO+ > My products",
                }
            response.raise_for_status()
            next(response.iter_bytes(), b"")
            return {"ready": True, "product": "FES2022b ocean_tide_extrapolated"}
    except httpx.HTTPError as exc:
        return {"ready": False, "reason": f"AVISO access check failed ({type(exc).__name__})"}


def fetch_catalog() -> list[CatalogEntry]:
    with _client(authenticated=False) as client:
        response = client.get(CATALOG_URL)
        response.raise_for_status()
    return parse_catalog(response.content)


def _download(client: httpx.Client, entry: CatalogEntry, directory: Path) -> Path:
    destination = directory / entry.name
    partial = destination.with_suffix(destination.suffix + ".part")
    # Completed files are only moved into place after the HTTP byte count has
    # been validated. Catalogue sizes are rounded to one decimal MB and cannot
    # be used as exact checksums.
    if destination.is_file() and destination.stat().st_size > 0:
        return destination
    if destination.exists():
        destination.unlink()

    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    url = f"{FILE_SERVER_BASE}{entry.url_path}"
    with client.stream("GET", url, headers=headers) as response:
        if response.status_code == 401:
            raise RuntimeError("AVISO rejected the credentials or the FES product is not enabled")
        if offset and response.status_code == 200:
            partial.unlink(missing_ok=True)
            offset = 0
        elif offset and response.status_code != 206:
            response.raise_for_status()
        else:
            response.raise_for_status()
        content_range = response.headers.get("Content-Range", "")
        expected_total: int | None = None
        if "/" in content_range:
            total = content_range.rsplit("/", 1)[-1]
            if total.isdigit():
                expected_total = int(total)
        if expected_total is None and response.headers.get("Content-Length", "").isdigit():
            expected_total = offset + int(response.headers["Content-Length"])
        mode = "ab" if offset else "wb"
        with partial.open(mode) as stream:
            for chunk in response.iter_bytes(1024 * 1024):
                stream.write(chunk)

    if expected_total is not None and partial.stat().st_size != expected_total:
        raise RuntimeError(f"incomplete AVISO download for {entry.name}")
    partial.replace(destination)
    return destination


def _decompress(archive: Path, destination: Path) -> None:
    if destination.is_file():
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    with lzma.open(archive, "rb") as source, partial.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)
    partial.replace(destination)


def pyfes_config_text() -> str:
    lines = [
        "tide:",
        "  cartesian:",
        "    amplitude: amplitude",
        "    dynamic:",
        "    - A5",
        "    latitude: lat",
        "    longitude: lon",
        "    paths:",
    ]
    for constituent, filename in CONSTITUENTS.items():
        lines.append(f"      {constituent}: ./ocean_tide_extrapolated/{filename}_fes2022.nc")
    lines.append("    phase: phase")
    return "\n".join(lines) + "\n"


def _download_land(client: httpx.Client, destination: Path) -> None:
    if destination.is_file():
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    with client.stream("GET", LAND_URL) as response:
        response.raise_for_status()
        with partial.open("wb") as stream:
            for chunk in response.iter_bytes(1024 * 1024):
                stream.write(chunk)
    partial.replace(destination)


def write_metadata(target: Path, accepted: datetime) -> dict[str, str]:
    atlas = target / "ocean_tide_extrapolated"
    config = target / "fes2022.yaml"
    mask = atlas / MASK_ARCHIVE.removesuffix(".xz")
    land = target / "natural-earth-ne-10m-land.geojson"
    manifest = target / "tide-assets.json"
    env_file = target / "worker.env"

    config.write_text(pyfes_config_text(), encoding="utf-8", newline="\n")
    files = [
        {"role": "pyfes_config", "path": config.name, "sha256": _digest(config)},
        {
            "role": "mask",
            "path": mask.relative_to(target).as_posix(),
            "sha256": _digest(mask),
        },
        {"role": "land_geojson", "path": land.name, "sha256": _digest(land)},
    ]
    for constituent, filename in CONSTITUENTS.items():
        path = atlas / f"{filename}_fes2022.nc"
        files.append(
            {
                "role": f"constituent:{constituent}",
                "path": path.relative_to(target).as_posix(),
                "sha256": _digest(path),
            }
        )

    payload = {
        "model_name": "FES2022b",
        "model_version": "2022b",
        "license_accepted_at": accepted.isoformat().replace("+00:00", "Z"),
        "license_review_due_at": _review_due(accepted).isoformat().replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "land_source_url": LAND_URL,
        "files": files,
    }
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    env_file.write_text(
        "\n".join(
            [
                f"TIDE_MODEL_DIR={target}",
                f"TIDE_PYFES_CONFIG={config}",
                f"TIDE_MASK_FILE={mask}",
                f"TIDE_LAND_GEOJSON={land}",
                f"TIDE_ASSET_MANIFEST={manifest}",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    try:
        env_file.chmod(0o600)
    except OSError:
        pass
    return {
        "model_dir": str(target),
        "pyfes_config": str(config),
        "mask": str(mask),
        "land_geojson": str(land),
        "manifest": str(manifest),
        "worker_env": str(env_file),
    }


def install(target_raw: str, license_accepted_at: str, *, keep_archives: bool) -> dict:
    target = validate_target(Path(target_raw))
    accepted = _instant(license_accepted_at)
    access = check_access()
    if not access["ready"]:
        raise RuntimeError(access["reason"])
    entries = fetch_catalog()
    compressed_bytes = sum(entry.size_bytes for entry in entries)
    target.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(target).free
    # Download plus unpacking needs substantially more than the catalogue size.
    required_bytes = compressed_bytes * 3
    if free_bytes < required_bytes:
        raise RuntimeError(
            f"not enough free disk space: need at least {required_bytes // 1_000_000_000} GB"
        )

    atlas = target / "ocean_tide_extrapolated"
    archives = target / "downloads"
    atlas.mkdir(exist_ok=True)
    archives.mkdir(exist_ok=True)
    with _client(authenticated=True) as client:
        for entry in entries:
            archive = _download(client, entry, archives)
            _decompress(archive, atlas / entry.name.removesuffix(".xz"))
            if not keep_archives:
                archive.unlink()
        with _client(authenticated=False) as public_client:
            _download_land(public_client, target / "natural-earth-ne-10m-land.geojson")

    paths = write_metadata(target, accepted)
    return {
        "ready_for_preflight": True,
        "downloaded_files": len(entries),
        "compressed_bytes": compressed_bytes,
        **paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Install private AVISO FES2022b worker assets")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("access", help="verify credentials and FES product access")
    plan = commands.add_parser("plan", help="show the current official atlas inventory")
    plan.add_argument("--target", required=True)
    setup = commands.add_parser("install", help="download, unpack and inventory FES2022b")
    setup.add_argument("--target", required=True)
    setup.add_argument("--license-accepted-at", required=True)
    setup.add_argument("--keep-archives", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "access":
            result = check_access()
        elif args.command == "plan":
            target = validate_target(Path(args.target))
            entries = fetch_catalog()
            result = {
                "target": str(target),
                "files": len(entries),
                "compressed_bytes": sum(item.size_bytes for item in entries),
                "minimum_free_bytes": sum(item.size_bytes for item in entries) * 3,
            }
        else:
            result = install(
                args.target,
                args.license_accepted_at,
                keep_archives=args.keep_archives,
            )
        _json(result)
        if result.get("ready") is False:
            raise SystemExit(1)
    except (OSError, ValueError, RuntimeError, httpx.HTTPError, lzma.LZMAError) as exc:
        _json({"ready": False, "error": str(exc)})
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
