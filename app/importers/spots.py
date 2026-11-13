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
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.spots import create_spot
from app.admin.constants import SPORTS
from app.admin.duplicates import find_spot_duplicates
from app.db.session import SessionLocal
from app.media.image_object import CANONICAL_KEYS, build_image
from app.models import Region, Spot, SpotContentSource
from app.names import normalize_name
from app.schemas.admin import SpotCreate
from app.config import get_settings


ARRAY_FIELDS = {
    "sports", "water_type", "bottom_type", "level", "best_wind_directions",
    "water_character", "style", "aliases",
}
JSON_FIELDS = {"editorial", "facilities", "image", "variant_conditions"}
ALLOWED_FIELDS = {
    "slug", "name", "region_slug", "lat", "lon", "location", "description",
    "facing", "model_pref", "editorial_classification", "sources",
    *ARRAY_FIELDS, *JSON_FIELDS,
}
REQUIRED_FIELDS = {"slug", "name", "region_slug", "sports"}
SOURCE_STATUSES = {"unreviewed", "verified", "rejected", "conflict"}
SOURCE_FIELD_PATH = re.compile(r"^[A-Za-z0-9_.:-]+$")


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
    preview: list[dict[str, Any]] = field(default_factory=list)
    source_records: int = 0

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
            "preview": self.preview,
            "source_records": self.source_records,
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


def _parse_checked_at(value: Any, *, source_number: int) -> datetime:
    if isinstance(value, datetime):
        checked_at = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            checked_at = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ImportFormatError(
                f"sources[{source_number}].checked_at: ISO-Zeitstempel erwartet"
            ) from exc
    else:
        raise ImportFormatError(f"sources[{source_number}].checked_at fehlt")
    if checked_at.tzinfo is None:
        raise ImportFormatError(
            f"sources[{source_number}].checked_at: Zeitzone erforderlich"
        )
    return checked_at


def _clean_source_text(
    source: dict[str, Any], key: str, source_number: int, *, required: bool, max_length: int
) -> str | None:
    value = source.get(key)
    if value is None:
        if required:
            raise ImportFormatError(f"sources[{source_number}].{key} fehlt")
        return None
    if not isinstance(value, str):
        raise ImportFormatError(f"sources[{source_number}].{key}: Text erwartet")
    value = " ".join(value.split())
    if required and not value:
        raise ImportFormatError(f"sources[{source_number}].{key} fehlt")
    if len(value) > max_length:
        raise ImportFormatError(
            f"sources[{source_number}].{key}: maximal {max_length} Zeichen"
        )
    return value or None


def _parse_sources(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    parsed = _parse_json_cell(value, "sources")
    if not isinstance(parsed, list):
        raise ImportFormatError("sources: erwartet eine Liste")
    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for number, source in enumerate(parsed, start=1):
        if not isinstance(source, dict):
            raise ImportFormatError(f"sources[{number}]: Objekt erwartet")
        unknown = sorted(
            set(source)
            - {"field_path", "url", "title", "publisher", "checked_at", "verification_status", "note"}
        )
        if unknown:
            raise ImportFormatError(
                f"sources[{number}]: unbekannte Felder: {', '.join(unknown)}"
            )
        field_path = _clean_source_text(
            source, "field_path", number, required=True, max_length=160
        )
        if not SOURCE_FIELD_PATH.fullmatch(field_path or ""):
            raise ImportFormatError(
                f"sources[{number}].field_path: ungültiger Feldpfad"
            )
        url = _clean_source_text(source, "url", number, required=True, max_length=2048)
        parts = urlsplit(url or "")
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ImportFormatError(f"sources[{number}].url: HTTP(S)-URL erwartet")
        title = _clean_source_text(source, "title", number, required=True, max_length=300)
        publisher = _clean_source_text(
            source, "publisher", number, required=False, max_length=200
        )
        note = _clean_source_text(source, "note", number, required=False, max_length=1000)
        status = source.get("verification_status", "unreviewed")
        if status not in SOURCE_STATUSES:
            raise ImportFormatError(
                f"sources[{number}].verification_status: ungültiger Wert {status!r}"
            )
        key = (field_path or "", url or "")
        if key in seen:
            raise ImportFormatError(
                f"sources[{number}]: Feldpfad und URL mehrfach im Spot"
            )
        seen.add(key)
        cleaned.append({
            "field_path": field_path,
            "url": url,
            "title": title,
            "publisher": publisher,
            "checked_at": _parse_checked_at(source.get("checked_at"), source_number=number),
            "verification_status": status,
            "note": note,
        })
    return cleaned


def _unwrap_spot_row(row: dict[str, Any]) -> dict[str, Any]:
    """Accept either a flat row or ``{"spot": {...}, "sources": [...]}``."""
    if "spot" not in row:
        return row
    unknown = sorted(set(row) - {"spot", "sources"})
    if unknown:
        raise ImportFormatError(
            f"Spot-Umschlag enthält unbekannte Felder: {', '.join(unknown)}"
        )
    spot = row.get("spot")
    if not isinstance(spot, dict):
        raise ImportFormatError("spot: Objekt erwartet")
    if "sources" in spot and "sources" in row:
        raise ImportFormatError("sources darf nur einmal angegeben werden")
    return {**spot, **({"sources": row["sources"]} if "sources" in row else {})}


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
        return [_unwrap_spot_row(row) for row in payload]
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

    row["sources"] = _parse_sources(row.get("sources"))

    if row.get("image") is not None:
        try:
            row["image"] = build_image(
                **{key: row["image"].get(key) for key in CANONICAL_KEYS}
            )
        except (TypeError, ValueError) as exc:
            raise ImportFormatError(f"image: {exc}") from exc

    editorial = dict(row.get("editorial") or {})
    aliases = row.pop("aliases", [])
    if aliases:
        existing_aliases = editorial.get("aliases") or []
        if not isinstance(existing_aliases, list):
            raise ImportFormatError("editorial.aliases: erwartet eine Liste")
        editorial["aliases"] = list(dict.fromkeys(
            str(alias).strip()
            for alias in [*existing_aliases, *aliases]
            if str(alias).strip()
        ))
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
    settings = get_settings()
    if not dry_run and settings.database_target != "local" and not settings.allow_remote_writes:
        raise ImportFormatError(
            "Batch-Import schreibt nur in eine lokale Datenbank. Für Remote-Ziele "
            "ist ein ausdrücklich freigegebener Deployment-Workflow erforderlich."
        )
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
            image = payload.pop("image", None)
            sources = payload.pop("sources", [])
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
                report.preview.append({
                    "row": number, "slug": slug, "action": "skip_existing",
                    "region": region.slug,
                })
                continue
            duplicate_result = find_spot_duplicates(
                db,
                name=row["name"],
                region_id=region.id,
                lat=row["lat"],
                lon=row["lon"],
                aliases=(row.get("editorial") or {}).get("aliases") or [],
            )
            candidates = [*duplicate_result.exact, *duplicate_result.likely]
            if duplicate_result.exact:
                report.skipped.append(slug)
                report.preview.append({
                    "row": number, "slug": slug, "action": "skip_exact_duplicate",
                    "region": region.slug, "duplicates": candidates,
                })
                continue
            spot = create_spot(
                validated.to_data(),
                db=db,
                actor=actor,
                commit=False,
                allow_duplicate=allow_duplicates,
            )
            if image is not None:
                spot.image = image
            for source in sources:
                db.add(SpotContentSource(
                    spot_id=spot.id,
                    **source,
                    created_by=actor,
                    reviewed_by=actor if source["verification_status"] == "verified" else None,
                ))
            report.source_records += len(sources)
            report.created.append(slug)
            report.preview.append({
                "row": number,
                "slug": slug,
                "action": "would_create" if dry_run else "created",
                "region": region.slug,
                "status": "draft",
                "image_rights_present": image is not None,
                "source_records": len(sources),
                "duplicates": candidates,
            })
        except Exception as exc:
            report.errors.append({"row": number, "slug": slug, "error": str(exc)})
            break

    if report.errors:
        rolled_back = set(report.created)
        for item in report.preview:
            if item.get("slug") in rolled_back and item.get("action") == "created":
                item["action"] = "rolled_back"
        report.created.clear()
        report.source_records = 0
        db.rollback()
    elif dry_run:
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
