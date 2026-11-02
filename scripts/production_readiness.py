"""Secret-safe production preflight and public API smoke checks."""

import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.config import _normalize_pg_driver
from app.db.schema import EXPECTED_DB_FINGERPRINT, EXPECTED_DB_REVISION


def _fail(label: str, exc: BaseException | None = None) -> None:
    suffix = f" ({type(exc).__name__})" if exc else ""
    print(f"ERROR: {label}{suffix}", file=sys.stderr)
    raise SystemExit(1)


def _connect(url: str, label: str):
    if not url:
        _fail(f"{label} database secret is not configured")
    try:
        engine = create_engine(
            _normalize_pg_driver(url),
            poolclass=NullPool,
            connect_args={"prepare_threshold": None},
        )
        connection = engine.connect()
        connection.execute(text("SELECT 1"))
        print(f"{label} connection: ok")
        return connection
    except Exception as exc:
        _fail(f"{label} connection failed", exc)


def _database_state(connection, label: str) -> tuple[tuple[str, ...], str | None]:
    try:
        revisions = tuple(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
        )
    except Exception as exc:
        _fail(f"{label} current schema revision could not be read", exc)
    if len(revisions) > 1:
        _fail(f"{label} database contains multiple Alembic revisions")
    try:
        count, latest = connection.execute(text(
            "SELECT count(id), max(updated_at) FROM spots WHERE status = 'published'"
        )).one()
        latest_token = latest.isoformat() if latest is not None else "none"
        catalog_version = f"{count}:{latest_token}"
    except Exception:
        # A database before the initial catalogue migration has no token yet.
        # Postflight verification requires it once the target is reached.
        catalog_version = None
    return revisions, catalog_version


def _short_fingerprint(value: str | None) -> str:
    return "unavailable" if value is None else sha256(value.encode("utf-8")).hexdigest()[:12]


def _write_github_outputs(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        _fail("GITHUB_OUTPUT is not configured")
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                _fail(f"unsafe newline in GitHub output {key}")
            handle.write(f"{key}={value}\n")


def database_preflight(require_target: bool, *, github_output: bool = False) -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if heads != [EXPECTED_DB_REVISION]:
        _fail(f"repository must have one Alembic head equal to {EXPECTED_DB_REVISION}")
    print(f"target revision: {EXPECTED_DB_REVISION}")

    direct = _connect(os.environ.get("DIRECT_DATABASE_URL", ""), "direct")
    try:
        direct_revisions, direct_catalog = _database_state(direct, "direct")
    finally:
        direct.close()
    current = direct_revisions[0] if direct_revisions else "base/unversioned"
    print(f"current revision: {current}")
    known_ancestors = {
        revision.revision
        for revision in script.walk_revisions(base="base", head=EXPECTED_DB_REVISION)
    }
    if direct_revisions and direct_revisions[0] not in known_ancestors:
        _fail("current revision is not an ancestor of the target")
    if require_target and direct_revisions != (EXPECTED_DB_REVISION,):
        _fail("database did not reach the target revision")

    pooled = _connect(os.environ.get("POOLED_DATABASE_URL", ""), "pooled")
    try:
        pooled_revisions, pooled_catalog = _database_state(pooled, "pooled")
    finally:
        pooled.close()
    if pooled_revisions != direct_revisions:
        _fail("direct and pooled connections report different schema revisions")
    if pooled_catalog != direct_catalog:
        _fail("direct and pooled connections report different public catalogues")
    if require_target and direct_catalog is None:
        _fail("target database has no readable public catalogue")
    print(f"catalog fingerprint: {_short_fingerprint(direct_catalog)}")
    print("direct/pooled schema and catalogue: identical")
    if github_output:
        if direct_catalog is None:
            _fail("catalogue attestation is unavailable")
        _write_github_outputs({
            "schema_fingerprint": EXPECTED_DB_FINGERPRINT,
            "catalog_version": direct_catalog,
        })


def _get_json(base_url: str, path: str):
    request = Request(base_url.rstrip("/") + path, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                _fail(f"GET {path} returned HTTP {response.status}")
            return json.load(response)
    except Exception as exc:
        _fail(f"GET {path} failed", exc)


def wave_api_smoke(base_url: str) -> None:
    wave_health = _get_json(base_url, "/weather-fields/waves/health")
    if wave_health.get("status") != "ok":
        _fail("wave-field health did not report ok")
    for name in ("primary", "fallback", "extended"):
        product = wave_health.get(name) or {}
        if not (product.get("active_publication") or {}).get("publication_id"):
            _fail(f"wave-field {name} has no active publication")

    manifest = _get_json(base_url, "/weather-fields/waves?lat=54.4&lon=11.2")
    valid_times = (manifest.get("manifest") or {}).get("valid_times") or []
    if not manifest.get("publication_id") or not valid_times:
        _fail("wave-field manifest has no publication or valid times")
    query = urlencode(
        {"lat": 54.4, "lon": 11.2, "valid_at": valid_times[0]}
    )
    sample = _get_json(base_url, f"/weather-fields/waves/sample?{query}")
    if sample.get("total_wave_height_m") is None:
        _fail("wave-field sample returned no total wave height")
    series = _get_json(
        base_url,
        "/weather-fields/waves/sample/series?lat=54.4&lon=11.2",
    )
    samples = series.get("samples") or []
    if not samples:
        _fail("wave-field series returned no samples")
    extended_source = next(
        (
            source
            for source in series.get("sources") or []
            if source.get("model") == "noaa-gfs-wave"
        ),
        None,
    )
    if extended_source is None:
        _fail("wave-field series has no NOAA GFS-Wave source")
    model_run = datetime.fromisoformat(
        extended_source["model_run"].replace("Z", "+00:00")
    )
    valid_to = datetime.fromisoformat(
        extended_source["valid_to"].replace("Z", "+00:00")
    )
    if valid_to - model_run < timedelta(hours=240):
        _fail("NOAA GFS-Wave publication does not reach T+240")
    extended_query = urlencode(
        {"lat": 54.4, "lon": 11.2, "valid_at": extended_source["valid_to"]}
    )
    extended = _get_json(base_url, f"/weather-fields/waves?{extended_query}")
    if (extended.get("selection") or {}).get("selected_model") != "noaa-gfs-wave":
        _fail("ten-day wave tail did not select NOAA GFS-Wave")
    print("EWAM/GWAM/GFS-Wave ten-day health, manifests, and point series: ok")


def api_smoke(*, require_wave_fields: bool = False) -> None:
    base_url = os.environ.get("PRODUCTION_API_BASE_URL", "")
    if not base_url.startswith("https://"):
        _fail("PRODUCTION_API_BASE_URL must be an HTTPS URL")
    health = _get_json(base_url, "/health/ready")
    if health.get("db") != "ok" or health.get("schema") != "ok":
        _fail("readiness did not report database and schema as ok")
    expected_schema = os.environ.get("EXPECTED_SCHEMA_FINGERPRINT")
    if expected_schema and health.get("schema_fingerprint") != expected_schema:
        _fail("readiness schema fingerprint differs from the migration postflight")
    print("readiness: ok")
    version = _get_json(base_url, "/spots/version")
    expected_catalog = os.environ.get("EXPECTED_CATALOG_VERSION")
    if expected_catalog and version.get("version") != expected_catalog:
        _fail("public API catalogue differs from the migration postflight")
    spots = _get_json(base_url, "/spots?limit=1")
    if not isinstance(spots, list) or not spots or not spots[0].get("id"):
        _fail("spot list did not return a smoke-test candidate")
    spot_id = spots[0]["id"]
    spot_reference = spots[0].get("slug") or spot_id
    print("spot version and list: ok")
    _get_json(base_url, f"/spots/{spot_reference}")
    regions = _get_json(base_url, "/regions?limit=1")
    if not isinstance(regions, list) or not regions or not regions[0].get("id"):
        _fail("region list did not return a smoke-test candidate")
    query = urlencode({"q": spots[0].get("name") or spot_reference})
    search = _get_json(base_url, f"/search?{query}")
    if not isinstance(search, dict) or not (search.get("spots") or search.get("regionen")):
        _fail("search did not return the smoke-test candidate")
    print("spot detail, regions, and search: ok")
    _get_json(base_url, f"/spots/{spot_id}/live")
    print("live value: ok")
    _get_json(base_url, f"/spots/{spot_id}/forecast")
    print("forecast: ok")
    if require_wave_fields:
        wave_api_smoke(base_url)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    database = commands.add_parser("database")
    database.add_argument("--require-target", action="store_true")
    database.add_argument("--github-output", action="store_true")
    api = commands.add_parser("api-smoke")
    api.add_argument("--require-wave-fields", action="store_true")
    args = parser.parse_args()
    if args.command == "database":
        database_preflight(args.require_target, github_output=args.github_output)
    else:
        api_smoke(require_wave_fields=args.require_wave_fields)


if __name__ == "__main__":
    main()
