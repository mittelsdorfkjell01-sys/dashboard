"""Pure Personal-Band calculation for a rider and sport.

The code owns no calibration numbers. It reads every factor from the supplied
versioned scoring-parameter payload; callers normally obtain that payload via
``app.scoring.params.get_params``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class PersonalBand:
    min_kt: float
    ideal_lo_kt: float
    ideal_hi_kt: float
    max_kt: float
    gust_tolerance_kt: float
    fingerprint: str


def _number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _items(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = profile.get("quiver", profile.get("gear", []))
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping) and item.get("active", True)]


def _quantize_wind(value: float) -> int:
    """Nearest 2 kt with deterministic half-up behaviour."""
    return int(math.floor(float(value) / 2.0 + 0.5) * 2)


def profile_fingerprint(
    band: PersonalBand | Mapping[str, Any],
    style_weights: Mapping[str, Any] | None,
    travel_mode: str | None,
) -> str:
    """Return a stable hash of coarse wind values and exact preference inputs."""
    def field(name: str) -> float:
        if isinstance(band, Mapping):
            return _number(band[name], name)
        return float(getattr(band, name))

    payload = {
        "wind_kt": [
            _quantize_wind(field("min_kt")),
            _quantize_wind(field("ideal_lo_kt")),
            _quantize_wind(field("ideal_hi_kt")),
            _quantize_wind(field("max_kt")),
            _quantize_wind(field("gust_tolerance_kt")),
        ],
        "style_weights": {
            str(key): int(value)
            for key, value in sorted((style_weights or {}).items())
        },
        "travel_mode": travel_mode or "day_trip",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def personal_band(profile: Mapping[str, Any], sport: str, params: Mapping[str, Any]) -> PersonalBand:
    """Calculate the Personal Band from weight, active gear, board and level."""
    try:
        model = params["rider_model"][sport]
        default = params["default_rider"][sport]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"rider model unavailable for {sport!r}") from exc

    weight = _number(profile.get("weight_kg", default.get("weight_kg")), "weight_kg")
    if not 30 <= weight <= 160:
        raise ValueError("weight_kg must be between 30 and 160")

    items = _items(profile)
    kites = [item for item in items if item.get("kind") == "kite" and item.get("size") is not None]
    # No usable kite means the versioned average quiver is used as-is, scaled
    # only by this rider's weight. A single real kite stays a single-kite band.
    band_items = items
    if not kites:
        band_items = _items({"quiver": default.get("quiver", [])})
        kites = [item for item in band_items if item.get("kind") == "kite" and item.get("size") is not None]
    if not kites:
        raise ValueError("default rider quiver must contain at least one kite")

    board_type = next(
        (
            "foil" if item.get("kind") == "foil" else str(item.get("board_type"))
            for item in band_items
            if item.get("kind") in {"board", "foil"} and (item.get("kind") == "foil" or item.get("board_type"))
        ),
        "twintip",
    )
    try:
        k_board = _number(model["k_board"][board_type], f"k_board.{board_type}")
        f_lo = _number(model["f_lo"], "f_lo")
        f_hi = _number(model["f_hi"], "f_hi")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid rider model for board type {board_type!r}") from exc
    if k_board <= 0 or not 0 < f_lo <= f_hi:
        raise ValueError("invalid Personal-Band calibration factors")

    cores = sorted(k_board * weight / _number(item["size"], "kite.size") for item in kites)
    if any(core <= 0 for core in cores):
        raise ValueError("kite sizes must be positive")

    level = str(profile.get("level") or default.get("level"))
    try:
        level_params = model["levels"][level]
        level_cap = _number(level_params["max_kt"], f"levels.{level}.max_kt")
        gust = _number(level_params["gust_tolerance_kt"], f"levels.{level}.gust_tolerance_kt")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"rider model unavailable for level {level!r}") from exc

    minimum = min(core * f_lo for core in cores)
    maximum = min(max(core * f_hi for core in cores), level_cap)
    # A safety cap can sit below the equipment's calculated lower edge (for
    # example a beginner with only a very small kite). Preserve an ordered,
    # degenerate band at the cap instead of silently exceeding the level cap.
    minimum = min(minimum, maximum)
    ideal_lo = max(minimum, min(cores))
    ideal_hi = min(maximum, max(cores))
    ideal_lo = min(max(ideal_lo, minimum), maximum)
    ideal_hi = min(max(ideal_hi, ideal_lo), maximum)
    raw = {
        "min_kt": minimum,
        "ideal_lo_kt": ideal_lo,
        "ideal_hi_kt": ideal_hi,
        "max_kt": maximum,
        "gust_tolerance_kt": gust,
    }
    fingerprint = profile_fingerprint(
        raw,
        profile.get("style_weights", default.get("style_weights", {})),
        str(profile.get("travel_mode") or default.get("travel_mode") or "day_trip"),
    )
    return PersonalBand(**raw, fingerprint=fingerprint)
