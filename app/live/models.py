"""Regional weather-model selection for Open-Meteo.

Open-Meteo can serve several regional models; the high-resolution ones only
cover a bounded domain, so we pick the best regional model for the spot's
coordinates and fall back to ``best_match`` (Open-Meteo's own blend) elsewhere.

Domains are approximate bounding boxes for the published model coverage and are
intentionally simple; a spot's ``model_pref`` (when set) always wins.
"""

from __future__ import annotations

# Open-Meteo `models` identifiers.
AROME = "meteofrance_arome_france_hd"  # Meteo-France AROME, France + coasts, ~1.3 km
ICON_D2 = "icon_d2"                    # DWD ICON-D2, central Europe, ~2 km
ICON_EU = "icon_eu"                    # DWD ICON-EU, Europe nest, ~7 km
BEST_MATCH = "best_match"             # Open-Meteo global blend

# Three independent global forecasting systems (DWD / NOAA / ECMWF). Their
# disagreement is the honest structural spread used for the Sprint 18 consensus
# band. ``best_match`` is deliberately excluded from the set: it is itself a
# blend, not an independent member.
CONSENSUS_GLOBAL_MODELS = [
    "ecmwf_ifs", "ncep_gfs_global", "ecmwf_aifs025_single", "icon_global"
]

# Legacy / invalid ``model_pref`` values → the valid Open-Meteo id. Open-Meteo
# has no bare ``icon`` model (it 400s the whole request); ``icon_seamless`` is
# the ICON family's seamless product and auto-selects the best ICON domain
# (D2/EU/global) for the coordinate, so it is the right home model everywhere.
_MODEL_ALIASES = {"icon": "icon_seamless"}


def normalize_model(model: str | None) -> str | None:
    """Map a stored/legacy model id onto a currently-valid Open-Meteo id."""
    if not model:
        return model
    return _MODEL_ALIASES.get(model, model)


def _in_box(lat: float, lon: float, s: float, n: float, w: float, e: float) -> bool:
    return s <= lat <= n and w <= lon <= e


def select_model(lat: float, lon: float, pref: str | None = None) -> str:
    """Choose the preferred regional model for a coordinate.

    If ``pref`` is given (e.g. ``spots.model_pref``) it wins, normalized onto a
    valid Open-Meteo id. Otherwise the most specific covering regional model
    wins, falling back to ``best_match``.
    """
    if pref:
        return normalize_model(pref)

    # Meteo-France AROME — France and its immediate coastlines (checked first as
    # the highest-resolution option).
    if _in_box(lat, lon, 41.0, 51.5, -5.5, 9.5):
        return AROME

    # DWD ICON-D2 — central Europe (DE/AT/CH/BeNeLux/Alps).
    if _in_box(lat, lon, 43.2, 58.1, -3.9, 20.3):
        return ICON_D2

    # DWD ICON-EU — wider Europe nest.
    if _in_box(lat, lon, 29.5, 70.5, -23.5, 62.5):
        return ICON_EU

    return BEST_MATCH


def consensus_models(
    lat: float,
    lon: float,
    pref: str | None = None,
    globals_: list[str] | None = None,
) -> list[str]:
    """The set of models fetched together for the consensus + spread band.

    The spot's primary/home model (:func:`select_model`, honouring ``pref``)
    leads the list, followed by the independent global systems
    (:data:`CONSENSUS_GLOBAL_MODELS`, or ``globals_`` when configured). The
    generic ``best_match`` blend is never added as a member; when it is the only
    thing :func:`select_model` yields (mid-ocean spots), the set is just the
    globals -- so no spot ever falls out of the consensus.

    Deduplicated, stable order (primary first).
    """
    from app.weather.catalog import forecast_models

    primary = select_model(lat, lon, pref)
    members: list[str] = []
    if pref and primary != BEST_MATCH:
        members.append(primary)
    selected = globals_ or [spec.id for spec in forecast_models(lat, lon)]
    for m in selected:
        if m and m not in members:
            members.append(m)
    return members
