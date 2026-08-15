"""Transactional bulk import for regions from JSON or CSV.

The importer accepts canonical fields as well as the German review-list fields
``region_slug`` and ``region``. Missing centres can be derived from a spot
import file with ``--spots-file``.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.regions import create_region
from app.db.session import SessionLocal
from app.importers.spots import ImportFormatError
from app.models import Region
from app.names import normalize_name
from app.schemas.admin import RegionCreate


COUNTRY_CODES = {
    "deutschland": "DE",
    "dänemark": "DK",
    "frankreich": "FR",
    "griechenland": "GR",
    "grossbritannien": "GB",
    "irland": "IE",
    "island": "IS",
    "italien": "IT",
    "kroatien": "HR",
    "montenegro": "ME",
    "niederlande": "NL",
    "norwegen": "NO",
    "österreich": "AT",
    "polen": "PL",
    "portugal": "PT",
    "schweden": "SE",
    "schweiz": "CH",
    "spanien": "ES",
}


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


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ImportFormatError(f"Datei nicht gefunden: {path}")
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ImportFormatError(
                f"Ungültiges JSON: {exc.msg} (Zeile {exc.lineno})"
            ) from exc
        if isinstance(payload, dict):
            payload = payload.get("regions")
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise ImportFormatError("JSON muss eine Liste oder ein Objekt mit 'regions' sein")
        return payload
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ImportFormatError("Unterstützt werden nur .json- und .csv-Dateien")


def load_spot_centres(path: Path | None) -> dict[str, tuple[float, float, list[float]]]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportFormatError(f"Spotdatei kann nicht gelesen werden: {exc}") from exc
    rows = payload.get("spots") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ImportFormatError("Spotdatei muss eine Liste oder ein Objekt mit 'spots' sein")
    grouped: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        try:
            grouped.setdefault(str(row["region_slug"]), []).append(
                (float(row["lat"]), float(row["lon"]))
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ImportFormatError("Spotdatei enthält ungültige Regionskoordinaten") from exc
    result = {}
    for slug, points in grouped.items():
        lats = [point[0] for point in points]
        lons = [point[1] for point in points]
        # A small margin makes a one-spot region a usable area as well.
        margin = 0.1
        result[slug] = (
            statistics.median(lats),
            statistics.median(lons),
            [min(lons) - margin, min(lats) - margin, max(lons) + margin, max(lats) + margin],
        )
    return result


def normalize_row(
    raw: dict[str, Any], row_number: int, centres: dict[str, tuple[float, float, list[float]]]
) -> dict[str, Any]:
    slug = str(raw.get("slug") or raw.get("region_slug") or "").strip()
    name = str(raw.get("name") or raw.get("region") or "").strip()
    if not slug or not name:
        raise ImportFormatError("Pflichtfelder fehlen: slug, name")
    country = str(raw.get("country") or "").strip()
    if len(country) == 2 and country.isalpha():
        country = country.upper()
    else:
        country = COUNTRY_CODES.get(country.casefold(), "")
    if not country:
        raise ImportFormatError("country muss ein bekannter Ländername oder ISO-Code sein")

    lat, lon, bounds = raw.get("lat"), raw.get("lon"), None
    if lat in (None, "") and lon in (None, "") and slug in centres:
        lat, lon, bounds = centres[slug]
    if (lat in (None, "")) != (lon in (None, "")):
        raise ImportFormatError("lat und lon müssen gemeinsam angegeben werden")
    data: dict[str, Any] = {"slug": slug, "name": name, "country": country}
    if lat not in (None, ""):
        data.update(lat=float(lat), lon=float(lon))
    if bounds:
        data["bounds"] = bounds
    for key in ("description", "defaults", "season"):
        if raw.get(key) not in (None, ""):
            data[key] = raw[key]
    data["_row_number"] = row_number
    return data


def import_regions(
    path: Path,
    *,
    db: Session,
    spots_file: Path | None = None,
    dry_run: bool = False,
    allow_duplicates: bool = False,
    actor: str = "bulk-import",
) -> ImportReport:
    rows = load_rows(path)
    centres = load_spot_centres(spots_file)
    report = ImportReport(source=str(path), dry_run=dry_run, total=len(rows))
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, raw in enumerate(rows, start=2 if path.suffix.lower() == ".csv" else 1):
        try:
            row = normalize_row(raw, number, centres)
            if row["slug"] in seen:
                raise ImportFormatError(f"Slug mehrfach in Datei: {row['slug']}")
            seen.add(row["slug"])
            normalized.append(row)
        except (ImportFormatError, ValidationError, ValueError) as exc:
            report.errors.append({"row": number, "slug": raw.get("slug") or raw.get("region_slug"), "error": str(exc)})
    if report.errors:
        db.rollback()
        return report

    existing = set(db.scalars(select(Region.slug).where(Region.slug.in_(seen))).all())
    existing_names = {
        (region.normalized_name, region.country): region.slug
        for region in db.scalars(select(Region)).all()
    }
    for row in normalized:
        number = row.pop("_row_number")
        bounds = row.pop("bounds", None)
        slug = row["slug"]
        matching_slug = existing_names.get((normalize_name(row["name"]), row["country"]))
        if slug in existing or matching_slug is not None:
            report.skipped.append(slug)
            continue
        try:
            validated = RegionCreate.model_validate(row)
            data = validated.to_data()
            if bounds:
                data["bounds"] = bounds
            create_region(
                data,
                db=db,
                commit=False,
                allow_duplicate=allow_duplicates,
                actor=actor,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regionen transaktional aus CSV oder JSON importieren")
    parser.add_argument("file", type=Path)
    parser.add_argument("--spots-file", type=Path, help="Spotdatei zum Ableiten von Zentrum und Bounds")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-duplicates", action="store_true")
    parser.add_argument("--actor", default="bulk-import")
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        report = import_regions(
            args.file,
            db=db,
            spots_file=args.spots_file,
            dry_run=args.dry_run,
            allow_duplicates=args.allow_duplicates,
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
