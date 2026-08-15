"""Bulk-import spots from JSON or CSV through the canonical admin workflow.

Usage::

    python -m app.importers.spots spots.json --dry-run
    python -m app.importers.spots spots.csv

The importer is create-only and idempotent by explicit slug. Existing slugs are
reported as skipped. Every new spot is created as a draft; images, forecasts and
derived data are intentionally outside this import format.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.spots import create_spot
from app.admin.constants import SPORTS
from app.admin.duplicates import find_spot_duplicates
from app.db.session import SessionLocal
from app.models import Region, Spot
from app.names import normalize_name
from app.schemas.admin import SpotCreate


ARRAY_FIELDS = {
    "sports", "water_type", "bottom_type", "level", "water_character", "style"
}
JSON_FIELDS = {"editorial", "facilities"}
ALLOWED_FIELDS = {
    "slug", "name", "region_slug", "lat", "lon", "location", "description",
    "facing", "model_pref", *ARRAY_FIELDS, *JSON_FIELDS,
}
REQUIRED_FIELDS = {"slug", "name", "region_slug", "sports"}


class ImportFormatError(ValueError):
    """The source file or one of its rows cannot be normalized."""


@dataclass
class ImportReport:
    source: str
    dry_run: bool
    total: int = 0
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "dry_run": self.dry_run,
            "ok": self.ok,
            "total": self.total,
            "created": self.created,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def _parse_json_cell(value: Any, field_name: str) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ImportFormatError(f"{field_name}: ungültiges JSON ({exc.msg})") from exc


def _parse_array(value: Any, field_name: str) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("["):
        parsed = _parse_json_cell(text, field_name)
        if not isinstance(parsed, list):
            raise ImportFormatError(f"{field_name}: erwartet eine Liste")
        return [str(item).strip() for item in parsed if str(item).strip()]
    separator = "|" if "|" in text else ";"
    return [item.strip() for item in text.split(separator) if item.strip()]


def load_rows(path: Path) -> list[dict[str, Any]]:
    """Read a UTF-8 JSON/CSV file into raw row dictionaries."""
    if not path.is_file():
        raise ImportFormatError(f"Datei nicht gefunden: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ImportFormatError(f"Ungültiges JSON: {exc.msg} (Zeile {exc.lineno})") from exc
        if isinstance(payload, dict):
            payload = payload.get("spots")
        if not isinstance(payload, list):
            raise ImportFormatError("JSON muss eine Liste oder ein Objekt mit 'spots' sein")
        if not all(isinstance(row, dict) for row in payload):
            raise ImportFormatError("Jeder JSON-Eintrag muss ein Objekt sein")
        return payload
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ImportFormatError("Unterstützt werden nur .json- und .csv-Dateien")


def normalize_row(raw: dict[str, Any], row_number: int) -> dict[str, Any]:
    """Normalize CSV-friendly values into the canonical import shape."""
    unknown = sorted(key for key, value in raw.items() if key not in ALLOWED_FIELDS and value not in (None, ""))
    if unknown:
        raise ImportFormatError(f"unbekannte Felder: {', '.join(unknown)}")

    row = {key: value for key, value in raw.items() if key in ALLOWED_FIELDS and value not in (None, "")}
    missing = sorted(field for field in REQUIRED_FIELDS if not str(row.get(field, "")).strip())
    if missing:
        raise ImportFormatError(f"Pflichtfelder fehlen: {', '.join(missing)}")

    if "location" in row:
        location = _parse_json_cell(row.pop("location"), "location")
        if not isinstance(location, list) or len(location) != 2:
            raise ImportFormatError("location muss [Längengrad, Breitengrad] sein")
        row.setdefault("lon", location[0])
        row.setdefault("lat", location[1])
    if "lat" not in row or "lon" not in row:
        raise ImportFormatError("Pflichtfelder fehlen: lat, lon (oder location)")

    for field_name in ARRAY_FIELDS:
        row[field_name] = _parse_array(row.get(field_name), field_name)
    if not row["sports"]:
        raise ImportFormatError("sports muss mindestens einen Wert enthalten")
    invalid_sports = sorted(set(row["sports"]) - set(SPORTS))
    if invalid_sports:
        raise ImportFormatError(f"sports: unbekannte Werte: {', '.join(invalid_sports)}")
    for field_name in JSON_FIELDS:
        if field_name in row:
            row[field_name] = _parse_json_cell(row[field_name], field_name)
            if row[field_name] is not None and not isinstance(row[field_name], dict):
                raise ImportFormatError(f"{field_name}: erwartet ein JSON-Objekt")

    editorial = dict(row.get("editorial") or {})
    if "description" in row:
        editorial["description"] = str(row.pop("description")).strip()
    row["editorial"] = editorial or None

    try:
        row["lat"] = float(row["lat"])
        row["lon"] = float(row["lon"])
        if "facing" in row:
            row["facing"] = int(row["facing"])
    except (TypeError, ValueError) as exc:
        raise ImportFormatError("lat, lon und facing müssen Zahlen sein") from exc

    row["slug"] = str(row["slug"]).strip()
    row["name"] = str(row["name"]).strip()
    row["region_slug"] = str(row["region_slug"]).strip()
    row["_row_number"] = row_number
    return row


def import_spots(
    path: Path,
    *,
    db: Session,
    dry_run: bool = False,
    allow_duplicates: bool = False,
    region_aliases: dict[str, str] | None = None,
    actor: str = "bulk-import",
) -> ImportReport:
    raw_rows = load_rows(path)
    report = ImportReport(source=str(path), dry_run=dry_run, total=len(raw_rows))
    normalized: list[dict[str, Any]] = []

    seen_slugs: set[str] = set()
    for number, raw in enumerate(raw_rows, start=2 if path.suffix.lower() == ".csv" else 1):
        try:
            row = normalize_row(raw, number)
            if row["slug"] in seen_slugs:
                raise ImportFormatError(f"Slug mehrfach in Datei: {row['slug']}")
            seen_slugs.add(row["slug"])
            normalized.append(row)
        except (ImportFormatError, ValidationError) as exc:
            report.errors.append({"row": number, "slug": raw.get("slug"), "error": str(exc)})

    if report.errors:
        db.rollback()
        return report

    region_aliases = region_aliases or {}
    region_slugs = {
        region_aliases.get(row["region_slug"], row["region_slug"])
        for row in normalized
    }
    regions = {
        region.slug: region
        for region in db.scalars(select(Region).where(Region.slug.in_(region_slugs))).all()
    }

    for row in normalized:
        number = row.pop("_row_number")
        slug = row["slug"]
        try:
            source_region_slug = row.pop("region_slug")
            region = regions.get(region_aliases.get(source_region_slug, source_region_slug))
            if region is None:
                raise ImportFormatError("Region nicht gefunden")
            payload = {**row, "region_id": region.id, "allow_duplicate": allow_duplicates}
            validated = SpotCreate.model_validate(payload)
            existing_spot = db.scalar(
                select(Spot.id).where(
                    (Spot.slug == slug)
                    | (
                        (Spot.region_id == region.id)
                        & (Spot.normalized_name == normalize_name(row["name"]))
                    )
                )
            )
            if existing_spot is not None:
                report.skipped.append(slug)
                continue
            duplicate_result = find_spot_duplicates(
                db,
                name=row["name"],
                region_id=region.id,
                lat=row["lat"],
                lon=row["lon"],
            )
            candidates = [*duplicate_result.exact, *duplicate_result.likely]
            if any(candidate.get("similarity") == 1.0 for candidate in candidates):
                report.skipped.append(slug)
                continue
            create_spot(
                validated.to_data(),
                db=db,
                actor=actor,
                commit=False,
                allow_duplicate=allow_duplicates,
            )
            report.created.append(slug)
        except Exception as exc:
            report.errors.append({"row": number, "slug": slug, "error": str(exc)})
            break

    if report.errors or dry_run:
        db.rollback()
    else:
        db.commit()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spots transaktional aus CSV oder JSON importieren")
    parser.add_argument("file", type=Path, help="Pfad zu einer .csv- oder .json-Datei")
    parser.add_argument("--dry-run", action="store_true", help="validieren und simulieren, nichts speichern")
    parser.add_argument("--allow-duplicates", action="store_true", help="Ähnlichkeitswarnungen bewusst übergehen")
    parser.add_argument(
        "--region-alias",
        action="append",
        default=[],
        metavar="QUELLE=ZIEL",
        help="abweichenden Regions-Slug zuordnen (mehrfach möglich)",
    )
    parser.add_argument("--actor", default="bulk-import", help="Name für den Audit-Eintrag")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        region_aliases = dict(item.split("=", 1) for item in args.region_alias)
    except ValueError:
        print(json.dumps({"ok": False, "errors": [{"error": "--region-alias erwartet QUELLE=ZIEL"}]}, ensure_ascii=False, indent=2))
        return 2
    db = SessionLocal()
    try:
        report = import_spots(
            args.file,
            db=db,
            dry_run=args.dry_run,
            allow_duplicates=args.allow_duplicates,
            region_aliases=region_aliases,
            actor=args.actor,
        )
    except ImportFormatError as exc:
        print(json.dumps({"ok": False, "errors": [{"error": str(exc)}]}, ensure_ascii=False, indent=2))
        return 2
    finally:
        db.close()
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
