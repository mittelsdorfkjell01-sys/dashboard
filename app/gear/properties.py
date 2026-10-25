"""Canonical gear property names and validation rules.

The catalogue stores claim values as JSON so research can grow without a
database migration for every new fact.  This registry keeps that flexibility
from turning into an untyped collection of duplicate field names and units.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Literal


PropertyScope = Literal["version", "size", "color"]
ValueKind = Literal["number", "integer", "range", "text", "enum", "enum_or_number", "colorway"]


class PropertyValidationError(ValueError):
    """Raised when a staged claim does not satisfy the property contract."""


@dataclass(frozen=True)
class PropertyDefinition:
    field: str
    group: str
    kind: ValueKind
    scopes: tuple[PropertyScope, ...]
    units: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidatedProperty:
    field: str
    value: dict[str, Any]
    unit: str | None
    scope: PropertyScope
    group: str


def _definition(
    field: str,
    group: str,
    kind: ValueKind,
    scopes: tuple[PropertyScope, ...],
    *,
    units: tuple[str, ...] = (),
    choices: tuple[str, ...] = (),
) -> PropertyDefinition:
    return PropertyDefinition(field, group, kind, scopes, units, choices)


PROPERTY_REGISTRY: dict[str, PropertyDefinition] = {
    item.field: item for item in (
        _definition("model_year", "identity", "integer", ("version",)),
        _definition("edition", "identity", "integer", ("version",)),
        _definition("catalogue_presence", "identity", "text", ("version",)),
        _definition("available_size", "dimensions", "number", ("size",), units=("m²", "cm", "l")),
        _definition("weight_without_bag", "dimensions", "number", ("size",), units=("kg", "g")),
        _definition("strut_count", "construction", "integer", ("version", "size")),
        _definition("aspect_ratio", "geometry", "enum_or_number", ("version", "size"), choices=("low", "medium", "high")),
        _definition("kite_shape", "geometry", "enum", ("version",), choices=("c", "hybrid", "delta", "bow", "foil")),
        _definition("profile_depth", "geometry", "enum", ("version", "size"), choices=("shallow", "medium", "deep")),
        _definition("projected_area", "geometry", "number", ("size",), units=("m²",)),
        _definition("flat_span", "geometry", "number", ("size",), units=("m",)),
        _definition("projected_span", "geometry", "number", ("size",), units=("m",)),
        _definition("arc_ratio", "geometry", "number", ("size",)),
        _definition("chord_depth", "geometry", "number", ("size",), units=("m",)),
        _definition("tip_sweep", "geometry", "number", ("size",), units=("deg",)),
        _definition("leading_edge_diameter", "geometry", "number", ("size",), units=("cm",)),
        _definition("intended_use", "performance", "enum", ("version",), choices=("all-round", "big-air", "freeride", "freestyle", "foil", "light-wind", "race", "school", "wave")),
        _definition("bar_pressure", "performance", "enum", ("version",), choices=("low", "medium", "high")),
        _definition("depower", "performance", "enum", ("version",), choices=("low", "medium", "high")),
        _definition("skill_level", "performance", "enum", ("version",), choices=("beginner", "intermediate", "advanced", "expert")),
        _definition("canopy_material", "construction", "text", ("version",)),
        _definition("leading_edge_material", "construction", "text", ("version",)),
        _definition("valve_system", "construction", "text", ("version",)),
        _definition("one_pump_system", "construction", "enum", ("version",), choices=("yes", "no")),
        _definition("bar_compatibility", "compatibility", "text", ("version",)),
        _definition("line_length", "compatibility", "number", ("version", "size"), units=("m",)),
        _definition("colorway", "appearance", "colorway", ("color",)),
    )
}


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PropertyValidationError(f"{field}: expected a number")
    if value <= 0:
        raise PropertyValidationError(f"{field}: value must be greater than zero")
    return value


def validate_property(claim: dict[str, Any], *, default_scope: PropertyScope) -> ValidatedProperty:
    field = claim.get("field")
    definition = PROPERTY_REGISTRY.get(field)
    if definition is None:
        raise PropertyValidationError(f"unknown gear property: {field!r}")

    scope = claim.get("scope", default_scope)
    if scope not in definition.scopes:
        allowed = ", ".join(definition.scopes)
        raise PropertyValidationError(f"{field}: scope {scope!r} is invalid; expected {allowed}")

    unit = claim.get("unit")
    if definition.units:
        if unit not in definition.units:
            allowed = ", ".join(definition.units)
            raise PropertyValidationError(f"{field}: unit {unit!r} is invalid; expected {allowed}")
    elif unit is not None:
        raise PropertyValidationError(f"{field}: does not accept a unit")

    kind = definition.kind
    raw = claim.get("value")
    if kind == "integer":
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            raise PropertyValidationError(f"{field}: expected a positive integer")
        value = {"value": raw}
    elif kind == "number":
        value = {"value": _number(raw, field)}
    elif kind == "range":
        minimum = _number(claim.get("min"), field)
        maximum = _number(claim.get("max"), field)
        if minimum >= maximum:
            raise PropertyValidationError(f"{field}: min must be lower than max")
        value = {"min": minimum, "max": maximum}
    elif kind == "text":
        if not isinstance(raw, str) or not raw.strip():
            raise PropertyValidationError(f"{field}: expected non-empty text")
        value = {"value": raw.strip()}
    elif kind == "enum":
        if raw not in definition.choices:
            raise PropertyValidationError(f"{field}: unsupported value {raw!r}")
        value = {"value": raw}
    elif kind == "enum_or_number":
        if isinstance(raw, Real) and not isinstance(raw, bool):
            value = {"value": _number(raw, field)}
        elif raw in definition.choices:
            value = {"value": raw}
        else:
            raise PropertyValidationError(f"{field}: expected a positive number or {definition.choices}")
    else:
        code = claim.get("code")
        name = claim.get("name")
        if not isinstance(code, str) or not code.strip():
            raise PropertyValidationError("colorway: code is required")
        if not isinstance(name, str) or not name.strip():
            raise PropertyValidationError("colorway: name is required")
        value = {"code": code.strip(), "name": name.strip()}

    return ValidatedProperty(field, value, unit, scope, definition.group)


def public_property_registry() -> list[dict[str, Any]]:
    """Return a stable, JSON-compatible description for tooling and agents."""
    return [
        {
            "field": item.field,
            "group": item.group,
            "kind": item.kind,
            "scopes": list(item.scopes),
            "units": list(item.units),
            "choices": list(item.choices),
        }
        for item in PROPERTY_REGISTRY.values()
    ]
