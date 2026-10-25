"""Read-only catalogue queries and selection validation."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.gear.properties import PROPERTY_REGISTRY


CATEGORIES = {
    "kite", "surfboard", "kiteboard", "bar", "line_set", "harness", "wetsuit",
    "wing", "windsurf", "windsurf_sail", "windsurf_board", "foil",
    "foil_component", "pump", "accessory",
}


def _claim_payload(claim: GearClaim, source: GearSource) -> dict[str, Any]:
    definition = PROPERTY_REGISTRY.get(claim.field_name)
    return {
        "field": claim.field_name,
        "group": definition.group if definition else "other",
        "value": dict(claim.value),
        "unit": claim.unit,
        "status": claim.verification_status,
        "verifiedAt": claim.verified_at.isoformat() if claim.verified_at else None,
        "uncertainty": claim.uncertainty_note,
        "source": {
            "title": source.title,
            "publisher": source.publisher,
            "url": source.url,
            "type": source.source_type,
            "checkedAt": source.checked_at.isoformat(),
        },
    }


def _source_payload(source: GearSource) -> dict[str, Any]:
    return {
        "title": source.title,
        "publisher": source.publisher,
        "url": source.url,
        "type": source.source_type,
        "checkedAt": source.checked_at.isoformat(),
    }


def list_catalog(db: Session, category: str = "kite") -> list[dict[str, Any]]:
    if category not in CATEGORIES:
        raise ValueError("invalid gear category")

    rows = db.execute(
        select(GearSizeVariant, GearProductVersion, GearProduct, GearBrand)
        .join(GearProductVersion, GearSizeVariant.product_version_id == GearProductVersion.id)
        .join(GearProduct, GearProductVersion.product_id == GearProduct.id)
        .join(GearBrand, GearProduct.brand_id == GearBrand.id)
        .where(GearProduct.category == category, GearBrand.active.is_(True))
        .order_by(GearBrand.name, GearProduct.model_name, GearProductVersion.model_year, GearSizeVariant.numeric_value)
    ).all()
    if not rows:
        return []

    version_ids = {version.id for _, version, _, _ in rows}
    claim_rows = db.execute(
        select(GearClaim, GearSource)
        .join(GearSource, GearClaim.source_id == GearSource.id)
        .where(GearClaim.product_version_id.in_(version_ids))
        .order_by(GearClaim.field_name)
    ).all()
    claims_by_version: dict[uuid.UUID, list[tuple[GearClaim, GearSource]]] = defaultdict(list)
    for claim, source in claim_rows:
        claims_by_version[claim.product_version_id].append((claim, source))

    colors_by_version: dict[uuid.UUID, list[GearColorVariant]] = defaultdict(list)
    for color in db.scalars(
        select(GearColorVariant)
        .where(GearColorVariant.product_version_id.in_(version_ids))
        .order_by(GearColorVariant.code)
    ).all():
        colors_by_version[color.product_version_id].append(color)

    compatibility_rows = db.execute(
        select(GearCompatibility, GearSource)
        .join(GearSource, GearCompatibility.source_id == GearSource.id)
        .where(GearCompatibility.product_version_id.in_(version_ids))
        .order_by(GearCompatibility.target_category, GearCompatibility.relation_type)
    ).all()
    target_version_ids = {
        compatibility.target_product_version_id
        for compatibility, _ in compatibility_rows
        if compatibility.target_product_version_id is not None
    }
    target_products: dict[uuid.UUID, dict[str, Any]] = {}
    if target_version_ids:
        for target_version, target_product, target_brand in db.execute(
            select(GearProductVersion, GearProduct, GearBrand)
            .join(GearProduct, GearProductVersion.product_id == GearProduct.id)
            .join(GearBrand, GearProduct.brand_id == GearBrand.id)
            .where(GearProductVersion.id.in_(target_version_ids))
        ).all():
            target_products[target_version.id] = {
                "id": str(target_version.id),
                "brand": {"slug": target_brand.slug, "name": target_brand.name},
                "category": target_product.category,
                "name": target_product.model_name,
                "season": target_version.season_label,
            }

    compatibility_by_version: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    for compatibility, source in compatibility_rows:
        compatibility_by_version[compatibility.product_version_id].append({
            "targetCategory": compatibility.target_category,
            "targetProductVersionId": (
                str(compatibility.target_product_version_id)
                if compatibility.target_product_version_id else None
            ),
            "targetProduct": target_products.get(compatibility.target_product_version_id),
            "relation": compatibility.relation_type,
            "specification": dict(compatibility.specification or {}),
            "status": compatibility.verification_status,
            "verifiedAt": (
                compatibility.verified_at.isoformat() if compatibility.verified_at else None
            ),
            "notes": compatibility.notes,
            "source": _source_payload(source),
        })

    use_profiles_by_version: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    for profile, source in db.execute(
        select(GearUseProfile, GearSource)
        .join(GearSource, GearUseProfile.source_id == GearSource.id)
        .where(GearUseProfile.product_version_id.in_(version_ids))
        .order_by(GearUseProfile.sport, GearUseProfile.discipline, GearUseProfile.condition)
    ).all():
        use_profiles_by_version[profile.product_version_id].append({
            "sport": profile.sport,
            "discipline": profile.discipline,
            "condition": profile.condition,
            "suitability": profile.suitability,
            "sizeVariantId": str(profile.size_variant_id) if profile.size_variant_id else None,
            "status": profile.verification_status,
            "verifiedAt": profile.verified_at.isoformat() if profile.verified_at else None,
            "notes": profile.notes,
            "source": _source_payload(source),
        })

    result: list[dict[str, Any]] = []
    for size, version, product, brand in rows:
        applicable_claims = [
            _claim_payload(claim, source)
            for claim, source in claims_by_version[version.id]
            if claim.color_variant_id is None
            and (claim.size_variant_id is None or claim.size_variant_id == size.id)
        ]
        result.append({
            "catalogSizeVariantId": str(size.id),
            "brand": {"slug": brand.slug, "name": brand.name},
            "category": product.category,
            "name": product.model_name,
            "model": product.model_name,
            "subtype": product.subtype,
            "season": version.season_label,
            "modelYear": version.model_year,
            "identityStatus": version.identity_status,
            "size": {
                "label": size.label,
                "value": float(size.numeric_value) if size.numeric_value is not None else None,
                "unit": size.unit,
            },
            "colors": [{
                "id": str(color.id), "code": color.code, "name": color.name,
                "palette": dict(color.palette or {}),
                "specifications": [
                    _claim_payload(claim, source)
                    for claim, source in claims_by_version[version.id]
                    if claim.color_variant_id == color.id
                ],
            } for color in colors_by_version[version.id]],
            "specifications": applicable_claims,
            "compatibility": compatibility_by_version[version.id],
            "useProfiles": [
                profile for profile in use_profiles_by_version[version.id]
                if profile["sizeVariantId"] in (None, str(size.id))
            ],
        })
    return result


def selection_payload(
    db: Session, size_variant_id: uuid.UUID | None, color_variant_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    if size_variant_id is None:
        return None
    category = db.scalar(
        select(GearProduct.category)
        .join(GearProductVersion, GearProduct.id == GearProductVersion.product_id)
        .join(GearSizeVariant, GearProductVersion.id == GearSizeVariant.product_version_id)
        .where(GearSizeVariant.id == size_variant_id)
    )
    if category is None:
        raise ValueError("catalog size variant not found")
    options = list_catalog(db, category)
    selected = next(
        (item for item in options if item["catalogSizeVariantId"] == str(size_variant_id)), None
    )
    if selected is None:
        raise ValueError("catalog size variant not found")
    if color_variant_id is not None and not any(
        color["id"] == str(color_variant_id) for color in selected["colors"]
    ):
        raise ValueError("catalog color variant does not belong to the selected product")
    selected_color = next(
        (color for color in selected["colors"] if color["id"] == str(color_variant_id)), None
    ) if color_variant_id else None
    return {
        **selected,
        "selectedColorVariantId": str(color_variant_id) if color_variant_id else None,
        "specifications": [
            *selected["specifications"],
            *(selected_color["specifications"] if selected_color else []),
        ],
    }
