"""Lead-time weights and normalization safeguards for model families."""

from __future__ import annotations

from collections.abc import Iterable

from app.weather.contracts import ModelFamily

AIFS_MAX_NORMALIZED_WEIGHT = 0.10


def target_family_weights(lead_hours: float) -> dict[ModelFamily, float]:
    if lead_hours <= 48:
        return {
            ModelFamily.REGIONAL: 0.50,
            ModelFamily.IFS: 0.25,
            ModelFamily.GFS: 0.15,
            ModelFamily.AIFS: 0.10,
        }
    if lead_hours <= 120:
        return {
            ModelFamily.IFS: 0.35,
            ModelFamily.REGIONAL: 0.25,
            ModelFamily.GFS: 0.20,
            ModelFamily.AIFS: 0.10,
            ModelFamily.OTHER: 0.10,
        }
    return {
        ModelFamily.IFS: 0.40,
        ModelFamily.GFS: 0.30,
        ModelFamily.AIFS: 0.10,
        ModelFamily.ICON_GLOBAL: 0.10,
        ModelFamily.ENSEMBLE: 0.10,
    }


def normalized_model_weights(
    members: Iterable[tuple[str, ModelFamily]], lead_hours: float,
    multipliers: dict[str, float] | None = None,
) -> dict[str, float]:
    """Distribute family weight over available members and safely renormalize."""
    members = list(members)
    if not members:
        return {}
    targets = target_family_weights(lead_hours)
    grouped: dict[ModelFamily, list[str]] = {}
    for model_id, family in members:
        grouped.setdefault(family, []).append(model_id)

    raw: dict[str, float] = {}
    for family, model_ids in grouped.items():
        family_weight = targets.get(family, targets.get(ModelFamily.OTHER, 0.0))
        for model_id in model_ids:
            multiplier = max(0.5, min(2.0, (multipliers or {}).get(model_id, 1.0)))
            raw[model_id] = family_weight / len(model_ids) * multiplier
    total = sum(raw.values())
    if total <= 0:
        equal = 1.0 / len(members)
        return {model_id: equal for model_id, _ in members}
    normalized = {model_id: weight / total for model_id, weight in raw.items()}

    aifs_ids = [mid for mid, family in members if family == ModelFamily.AIFS]
    aifs_total = sum(normalized.get(mid, 0.0) for mid in aifs_ids)
    if aifs_total > AIFS_MAX_NORMALIZED_WEIGHT:
        scale = AIFS_MAX_NORMALIZED_WEIGHT / aifs_total
        for mid in aifs_ids:
            normalized[mid] *= scale
        remaining_ids = [mid for mid in normalized if mid not in aifs_ids]
        remaining_total = sum(normalized[mid] for mid in remaining_ids)
        if remaining_total > 0:
            factor = (1.0 - AIFS_MAX_NORMALIZED_WEIGHT) / remaining_total
            for mid in remaining_ids:
                normalized[mid] *= factor
    return normalized
