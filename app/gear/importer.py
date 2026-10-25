"""Validated import of reviewed gear research from the staging directory."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gear.properties import PropertyScope, ValidatedProperty, validate_property
from app.models import (
    GearBrand,
    GearClaim,
    GearColorVariant,
    GearCompatibility,
    GearProduct,
    GearProductVersion,
    GearSizeVariant,
    GearSource,
    GearUseProfile,
)


ACCEPTED_REVIEW_STATUSES = {"accepted_for_import", "accepted_for_initial_migration"}
VERIFICATION_STATUSES = {"unverified", "review", "verified", "conflict"}
SOURCE_TYPES = {"manufacturer_page", "manufacturer_manual", "manufacturer_catalog", "retailer", "other"}
CATEGORIES = {
    "kite", "surfboard", "kiteboard", "bar", "line_set", "harness", "wetsuit",
    "wing", "windsurf", "windsurf_sail", "windsurf_board", "foil",
    "foil_component", "pump", "accessory",
}
RELATION_TYPES = {"requires", "compatible", "recommended", "incompatible"}
SPORTS = {"kitesurf", "windsurf", "wingfoil", "surfing"}
DISCIPLINES = {"all_round", "freeride", "big_air", "wave", "freestyle", "foil", "race", "school"}
CONDITIONS = {"all_conditions", "light_wind", "moderate_wind", "strong_wind", "waves", "flat_water", "gusty"}
SUITABILITIES = {"designed_for", "suitable", "limited", "not_recommended"}


class GearImportError(ValueError):
    """Raised when staged research is incomplete, unsafe, or conflicts with the catalogue."""


@dataclass(frozen=True)
class StagedSource:
    url: str
    title: str
    publisher: str
    source_type: str
    checked_at: datetime
    rights_note: str


@dataclass(frozen=True)
class StagedClaim:
    property: ValidatedProperty
    status: str
    source: StagedSource
    uncertainty: str | None = None


@dataclass(frozen=True)
class StagedCompatibility:
    target_category: str
    target_brand: str | None
    target_model: str | None
    target_season: str | None
    relation: str
    specification: dict[str, Any]
    status: str
    source: StagedSource
    notes: str | None = None


@dataclass(frozen=True)
class StagedUseProfile:
    sport: str
    discipline: str
    condition: str
    suitability: str
    status: str
    source: StagedSource
    notes: str | None = None


@dataclass(frozen=True)
class StagedRecord:
    brand: str
    category: str
    model: str
    subtype: str | None
    season: str
    model_year: int | None
    size_label: str | None
    size_value: float | None
    size_unit: str | None
    claims: tuple[StagedClaim, ...]
    compatibilities: tuple[StagedCompatibility, ...]
    use_profiles: tuple[StagedUseProfile, ...]


@dataclass
class ImportSummary:
    records: int = 0
    created: dict[str, int] = field(default_factory=lambda: {
        "brands": 0, "products": 0, "versions": 0, "sizes": 0,
        "colors": 0, "sources": 0, "claims": 0, "compatibilities": 0,
        "useProfiles": 0,
    })
    skipped_claims: int = 0
    skipped_relations: int = 0


def _timestamp(raw: Any, label: str) -> datetime:
    if not isinstance(raw, str):
        raise GearImportError(f"{label}: ISO timestamp is required")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GearImportError(f"{label}: invalid ISO timestamp") from exc
    if value.tzinfo is None:
        raise GearImportError(f"{label}: timestamp must include a timezone")
    return value


def _source(
    raw: Any, *, brand: str, default_checked_at: datetime, default_rights: str,
) -> StagedSource:
    if isinstance(raw, str):
        raw = {"url": raw}
    if not isinstance(raw, dict):
        raise GearImportError("each claim needs a source URL or source object")
    url = raw.get("url")
    parsed = urlparse(url) if isinstance(url, str) else None
    if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise GearImportError("source.url must be an absolute HTTP(S) URL")
    source_type = raw.get("type", "manufacturer_page")
    if source_type not in SOURCE_TYPES:
        raise GearImportError(f"source.type {source_type!r} is invalid")
    rights = raw.get("rights", default_rights)
    if not isinstance(rights, str) or not rights.strip():
        raise GearImportError("source rights note is required")
    return StagedSource(
        url=url,
        title=str(raw.get("title") or f"{brand} product source"),
        publisher=str(raw.get("publisher") or brand),
        source_type=source_type,
        checked_at=_timestamp(raw["checkedAt"], "source.checkedAt") if "checkedAt" in raw else default_checked_at,
        rights_note=rights.strip(),
    )


def _size(record: dict[str, Any]) -> tuple[str | None, float | None, str | None]:
    raw = record.get("size")
    if raw is None:
        return None, None, None
    if isinstance(raw, dict):
        label, value, unit = raw.get("label"), raw.get("value"), raw.get("unit")
    elif isinstance(raw, str):
        match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(\S+)\s*", raw)
        if not match:
            raise GearImportError(f"size {raw!r} must contain a number and unit")
        label, value, unit = raw.strip(), float(match.group(1).replace(",", ".")), match.group(2)
    else:
        raise GearImportError("size must be a string or object")
    if not isinstance(label, str) or not label.strip() or not isinstance(value, (int, float)) or value <= 0:
        raise GearImportError("size needs a label and positive numeric value")
    if not isinstance(unit, str) or not unit:
        raise GearImportError("size unit is required")
    return label.strip(), float(value), unit


def validate_staging_document(document: dict[str, Any]) -> tuple[StagedRecord, ...]:
    if document.get("reviewStatus") not in ACCEPTED_REVIEW_STATUSES:
        raise GearImportError("staging document has not been accepted for import")
    checked_at = _timestamp(document.get("checkedAt"), "checkedAt")
    rights = document.get("rights")
    if not isinstance(rights, str) or not rights.strip():
        raise GearImportError("top-level rights note is required")
    raw_records = document.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise GearImportError("records must be a non-empty list")

    records: list[StagedRecord] = []
    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            raise GearImportError(f"records[{index}] must be an object")
        brand, model, season = raw.get("brand"), raw.get("name", raw.get("model")), raw.get("season")
        if not all(isinstance(value, str) and value.strip() for value in (brand, model, season)):
            raise GearImportError(f"records[{index}] needs brand, model and season")
        size_label, size_value, size_unit = _size(raw)
        default_source = raw.get("source")
        staged_claims: list[StagedClaim] = []
        for claim_index, claim in enumerate(raw.get("claims", [])):
            if not isinstance(claim, dict):
                raise GearImportError(f"records[{index}].claims[{claim_index}] must be an object")
            status = claim.get("status", "unverified")
            if status not in VERIFICATION_STATUSES:
                raise GearImportError(f"claim status {status!r} is invalid")
            field = claim.get("field")
            if field == "colorway":
                default_scope: PropertyScope = "color"
            elif size_label is not None and field in {
                "available_size", "weight_without_bag", "projected_area",
                "flat_span", "projected_span", "arc_ratio", "chord_depth", "tip_sweep",
                "leading_edge_diameter",
            }:
                default_scope = "size"
            else:
                default_scope = "version"
            try:
                prop = validate_property(claim, default_scope=default_scope)
            except ValueError as exc:
                raise GearImportError(f"records[{index}].claims[{claim_index}]: {exc}") from exc
            source = _source(
                claim.get("source", default_source), brand=brand,
                default_checked_at=checked_at, default_rights=rights,
            )
            uncertainty = claim.get("uncertainty")
            staged_claims.append(StagedClaim(prop, status, source, uncertainty))

        staged_compatibilities: list[StagedCompatibility] = []
        for item_index, item in enumerate(raw.get("compatibility", [])):
            if not isinstance(item, dict):
                raise GearImportError(f"records[{index}].compatibility[{item_index}] must be an object")
            target = item.get("targetCategory")
            relation = item.get("relation")
            status = item.get("status", "unverified")
            specification = item.get("specification", {})
            if target not in CATEGORIES:
                raise GearImportError(f"compatibility target category {target!r} is invalid")
            if relation not in RELATION_TYPES:
                raise GearImportError(f"compatibility relation {relation!r} is invalid")
            if status not in VERIFICATION_STATUSES:
                raise GearImportError(f"compatibility status {status!r} is invalid")
            if not isinstance(specification, dict):
                raise GearImportError("compatibility specification must be an object")
            target_product = item.get("targetProduct")
            target_brand = target_model = target_season = None
            if target_product is not None:
                if not isinstance(target_product, dict):
                    raise GearImportError("compatibility targetProduct must be an object")
                target_brand = target_product.get("brand")
                target_model = target_product.get("name", target_product.get("model"))
                target_season = target_product.get("season")
                if not all(
                    isinstance(value, str) and value.strip()
                    for value in (target_brand, target_model, target_season)
                ):
                    raise GearImportError(
                        "compatibility targetProduct needs brand, name and season"
                    )
                target_brand = target_brand.strip()
                target_model = target_model.strip()
                target_season = target_season.strip()
            staged_compatibilities.append(StagedCompatibility(
                target_category=target,
                target_brand=target_brand,
                target_model=target_model,
                target_season=target_season,
                relation=relation, specification=specification,
                status=status,
                source=_source(
                    item.get("source", default_source), brand=brand,
                    default_checked_at=checked_at, default_rights=rights,
                ),
                notes=item.get("notes") or item.get("uncertainty"),
            ))

        staged_use_profiles: list[StagedUseProfile] = []
        for item_index, item in enumerate(raw.get("useProfiles", [])):
            if not isinstance(item, dict):
                raise GearImportError(f"records[{index}].useProfiles[{item_index}] must be an object")
            sport = item.get("sport")
            discipline = item.get("discipline")
            condition = item.get("condition")
            suitability = item.get("suitability")
            status = item.get("status", "unverified")
            if sport not in SPORTS or discipline not in DISCIPLINES:
                raise GearImportError("use profile sport or discipline is invalid")
            if condition not in CONDITIONS or suitability not in SUITABILITIES:
                raise GearImportError("use profile condition or suitability is invalid")
            if status not in VERIFICATION_STATUSES:
                raise GearImportError(f"use profile status {status!r} is invalid")
            if "windRangeKn" in item:
                raise GearImportError(
                    "use profiles must not define windRangeKn; use a qualitative condition"
                )
            staged_use_profiles.append(StagedUseProfile(
                sport=sport, discipline=discipline, condition=condition,
                suitability=suitability, status=status,
                source=_source(
                    item.get("source", default_source), brand=brand,
                    default_checked_at=checked_at, default_rights=rights,
                ),
                notes=item.get("notes") or item.get("uncertainty"),
            ))

        if not staged_claims and not staged_compatibilities and not staged_use_profiles:
            raise GearImportError(f"records[{index}] has no claims, compatibility or use profiles")
        model_year = raw.get("modelYear")
        if model_year is not None and (isinstance(model_year, bool) or not isinstance(model_year, int) or model_year < 1900):
            raise GearImportError(f"records[{index}].modelYear is invalid")
        category = raw.get("category", "kite")
        if category not in CATEGORIES:
            raise GearImportError(f"records[{index}].category {category!r} is invalid")
        records.append(StagedRecord(
            brand=brand.strip(), category=category, model=model.strip(),
            subtype=raw.get("subtype"), season=season.strip(), model_year=model_year,
            size_label=size_label, size_value=size_value, size_unit=size_unit,
            claims=tuple(staged_claims),
            compatibilities=tuple(staged_compatibilities),
            use_profiles=tuple(staged_use_profiles),
        ))
    return tuple(records)


def load_staging_file(path: Path) -> tuple[StagedRecord, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GearImportError(f"cannot read staging file {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise GearImportError("staging document must be a JSON object")
    return validate_staging_document(document)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise GearImportError(f"cannot derive slug from brand {value!r}")
    return slug


def _get_or_create_source(db: Session, staged: StagedSource, summary: ImportSummary) -> GearSource:
    source = db.scalar(select(GearSource).where(GearSource.url == staged.url))
    if source is None:
        source = GearSource(
            url=staged.url, title=staged.title, publisher=staged.publisher,
            source_type=staged.source_type, checked_at=staged.checked_at,
            rights_note=staged.rights_note,
        )
        db.add(source)
        db.flush()
        summary.created["sources"] += 1
    return source


def import_staging_records(db: Session, records: tuple[StagedRecord, ...]) -> ImportSummary:
    """Add reviewed records without updating or deleting existing catalogue facts."""
    summary = ImportSummary(records=len(records))
    for record in records:
        brand = db.scalar(select(GearBrand).where(GearBrand.slug == _slug(record.brand)))
        if brand is None:
            brand = GearBrand(slug=_slug(record.brand), name=record.brand, active=True)
            db.add(brand)
            db.flush()
            summary.created["brands"] += 1
        elif brand.name != record.brand:
            raise GearImportError(f"brand slug collision: {record.brand!r} conflicts with {brand.name!r}")
        product = db.scalar(select(GearProduct).where(
            GearProduct.brand_id == brand.id, GearProduct.category == record.category,
            GearProduct.model_name == record.model,
        ))
        if product is None:
            product = GearProduct(brand_id=brand.id, category=record.category, model_name=record.model, subtype=record.subtype)
            db.add(product)
            db.flush()
            summary.created["products"] += 1
        elif product.subtype != record.subtype and record.subtype is not None:
            raise GearImportError(f"conflicting subtype for {record.brand} {record.model}")
        version = db.scalar(select(GearProductVersion).where(
            GearProductVersion.product_id == product.id,
            GearProductVersion.season_label == record.season,
        ))
        if version is None:
            version = GearProductVersion(
                product_id=product.id, season_label=record.season, model_year=record.model_year,
                identity_status="verified" if record.model_year else "review",
            )
            db.add(version)
            db.flush()
            summary.created["versions"] += 1
        elif version.model_year != record.model_year:
            raise GearImportError(f"conflicting model year for {record.brand} {record.model} {record.season}")

        size = None
        if record.size_label:
            size = db.scalar(select(GearSizeVariant).where(
                GearSizeVariant.product_version_id == version.id,
                GearSizeVariant.label == record.size_label,
            ))
            if size is None:
                size = GearSizeVariant(
                    product_version_id=version.id, label=record.size_label,
                    numeric_value=record.size_value, unit=record.size_unit,
                )
                db.add(size)
                db.flush()
                summary.created["sizes"] += 1
            elif float(size.numeric_value) != record.size_value or size.unit != record.size_unit:
                raise GearImportError(
                    f"conflicting size definition for {record.brand} {record.model} {record.size_label}"
                )

        for staged in record.claims:
            source = _get_or_create_source(db, staged.source, summary)

            color = None
            if staged.property.scope == "color":
                code = staged.property.value["code"]
                color = db.scalar(select(GearColorVariant).where(
                    GearColorVariant.product_version_id == version.id,
                    GearColorVariant.code == code,
                ))
                if color is None:
                    color = GearColorVariant(
                        product_version_id=version.id, code=code,
                        name=staged.property.value["name"], palette={},
                    )
                    db.add(color)
                    db.flush()
                    summary.created["colors"] += 1
                elif color.name != staged.property.value["name"]:
                    raise GearImportError(
                        f"conflicting color name for {record.brand} {record.model} {code}"
                    )

            size_id = size.id if staged.property.scope == "size" and size else None
            if staged.property.scope == "size" and size is None:
                raise GearImportError(f"{staged.property.field}: size-scoped claim needs a record size")
            color_id = color.id if color else None
            existing = db.scalars(select(GearClaim).where(
                GearClaim.product_version_id == version.id,
                GearClaim.field_name == staged.property.field,
                GearClaim.source_id == source.id,
                GearClaim.size_variant_id == size_id,
                GearClaim.color_variant_id == color_id,
            )).all()
            if existing:
                if any(
                    claim.value == staged.property.value
                    and claim.unit == staged.property.unit
                    and claim.verification_status == staged.status
                    for claim in existing
                ):
                    summary.skipped_claims += 1
                    continue
                raise GearImportError(
                    f"conflicting existing claim: {record.brand} {record.model} "
                    f"{record.season} {staged.property.field}"
                )
            db.add(GearClaim(
                product_version_id=version.id, size_variant_id=size_id,
                color_variant_id=color_id, field_name=staged.property.field,
                value=staged.property.value, unit=staged.property.unit,
                source_id=source.id, verification_status=staged.status,
                verified_at=staged.source.checked_at if staged.status == "verified" else None,
                uncertainty_note=staged.uncertainty,
            ))
            summary.created["claims"] += 1

        for staged in record.compatibilities:
            source = _get_or_create_source(db, staged.source, summary)
            target_version_id = None
            if staged.target_brand is not None:
                target_version_id = db.scalar(
                    select(GearProductVersion.id)
                    .join(GearProduct, GearProductVersion.product_id == GearProduct.id)
                    .join(GearBrand, GearProduct.brand_id == GearBrand.id)
                    .where(
                        GearBrand.slug == _slug(staged.target_brand),
                        GearProduct.category == staged.target_category,
                        GearProduct.model_name == staged.target_model,
                        GearProductVersion.season_label == staged.target_season,
                    )
                )
                if target_version_id is None:
                    raise GearImportError(
                        "compatibility target product not found: "
                        f"{staged.target_brand} {staged.target_model} {staged.target_season}"
                    )
            existing = db.scalars(select(GearCompatibility).where(
                GearCompatibility.product_version_id == version.id,
                GearCompatibility.target_category == staged.target_category,
                GearCompatibility.target_product_version_id == target_version_id,
                GearCompatibility.relation_type == staged.relation,
                GearCompatibility.source_id == source.id,
            )).all()
            if existing:
                if any(
                    item.specification == staged.specification
                    and item.verification_status == staged.status
                    for item in existing
                ):
                    summary.skipped_relations += 1
                    continue
                raise GearImportError(
                    f"conflicting compatibility: {record.brand} {record.model} "
                    f"{staged.target_category}"
                )
            db.add(GearCompatibility(
                product_version_id=version.id,
                target_category=staged.target_category,
                target_product_version_id=target_version_id,
                relation_type=staged.relation,
                specification=staged.specification,
                source_id=source.id,
                verification_status=staged.status,
                verified_at=staged.source.checked_at if staged.status == "verified" else None,
                notes=staged.notes,
            ))
            summary.created["compatibilities"] += 1

        for staged in record.use_profiles:
            source = _get_or_create_source(db, staged.source, summary)
            size_id = size.id if size else None
            existing = db.scalars(select(GearUseProfile).where(
                GearUseProfile.product_version_id == version.id,
                GearUseProfile.size_variant_id == size_id,
                GearUseProfile.sport == staged.sport,
                GearUseProfile.discipline == staged.discipline,
                GearUseProfile.condition == staged.condition,
                GearUseProfile.source_id == source.id,
            )).all()
            if existing:
                if any(
                    item.suitability == staged.suitability
                    and item.verification_status == staged.status
                    for item in existing
                ):
                    summary.skipped_relations += 1
                    continue
                raise GearImportError(
                    f"conflicting use profile: {record.brand} {record.model} "
                    f"{staged.sport}/{staged.discipline}/{staged.condition}"
                )
            db.add(GearUseProfile(
                product_version_id=version.id,
                size_variant_id=size_id,
                sport=staged.sport,
                discipline=staged.discipline,
                condition=staged.condition,
                suitability=staged.suitability,
                source_id=source.id,
                verification_status=staged.status,
                verified_at=staged.source.checked_at if staged.status == "verified" else None,
                notes=staged.notes,
            ))
            summary.created["useProfiles"] += 1
    db.flush()
    return summary
