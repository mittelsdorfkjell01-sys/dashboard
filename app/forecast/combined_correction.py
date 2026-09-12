"""Compose the independent GWA and microscale priors into one sector candidate.

GWA anchors the long-term 10 m wind level against ERA5.  Microscale supplies
the direction-dependent roughness/fetch transfer.  They describe independent
parts of the local adjustment, so the combined speed factor is their product,
subject to the same final safety clamp used by the individual producers.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.forecast.gwa_producer import FACTOR_HIGH, FACTOR_LOW, SectorFactor
from app.weather.physics.limits import clamp

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "combined_unavailable"


@dataclass(frozen=True)
class CombinedSectorResult:
    status: str
    sectors: list[SectorFactor]
    provenance: dict

    @property
    def enabled(self) -> bool:
        return self.status == STATUS_OK


def combine_sector_results(gwa, microscale) -> CombinedSectorResult:
    """Multiply matching canonical sectors, failing closed on incomplete input."""
    component_status = {
        "gwa": getattr(gwa, "status", "unknown"),
        "microscale": getattr(microscale, "status", "unknown"),
    }
    provenance = {
        "method": "gwa_x_microscale",
        "components": component_status,
        "gwa_version": getattr(gwa, "provenance", {}).get("gwa_version"),
        "reference_model": getattr(gwa, "provenance", {}).get("reference_model"),
        "reference_window": getattr(gwa, "provenance", {}).get("window"),
        "microscale_method": getattr(microscale, "provenance", {}).get("method"),
        "grid_cell": (
            getattr(microscale, "provenance", {}).get("grid_cell")
            or getattr(gwa, "provenance", {}).get("grid_cell")
        ),
    }
    if component_status != {"gwa": STATUS_OK, "microscale": STATUS_OK}:
        return CombinedSectorResult(STATUS_UNAVAILABLE, [], provenance)

    gwa_by_index = {int(row.index): row for row in getattr(gwa, "sectors", [])}
    micro_by_index = {
        int(row.index): row for row in getattr(microscale, "sectors", [])
    }
    if set(gwa_by_index) != set(range(12)) or set(micro_by_index) != set(range(12)):
        return CombinedSectorResult(STATUS_UNAVAILABLE, [], provenance)

    sectors = []
    for index in range(12):
        gwa_sector = gwa_by_index[index]
        micro_sector = micro_by_index[index]
        if (
            round(float(gwa_sector.start_deg) % 360.0, 6)
            != round(float(micro_sector.start_deg) % 360.0, 6)
            or round(float(gwa_sector.end_deg) % 360.0, 6)
            != round(float(micro_sector.end_deg) % 360.0, 6)
        ):
            return CombinedSectorResult(STATUS_UNAVAILABLE, [], provenance)
        raw_factor = float(gwa_sector.speed_factor) * float(
            micro_sector.speed_factor
        )
        factor = clamp(raw_factor, FACTOR_LOW, FACTOR_HIGH)
        raw_offset = float(gwa_sector.direction_offset_deg) + float(
            micro_sector.direction_offset_deg
        )
        offset = clamp(raw_offset, -15.0, 15.0)
        sector = SectorFactor(
            index=index,
            start_deg=float(gwa_sector.start_deg),
            end_deg=float(gwa_sector.end_deg),
            speed_factor=round(factor, 4),
            direction_offset_deg=round(offset, 3),
            confidence=(
                "low"
                if "low" in {gwa_sector.confidence, micro_sector.confidence}
                else "ok"
            ),
            saturated=(
                bool(gwa_sector.saturated)
                or bool(micro_sector.saturated)
                or factor != raw_factor
                or offset != raw_offset
            ),
        )
        # Frozen dataclasses cannot carry dynamic audit attributes.  The runner
        # reconstructs these two component values by index for the sector note.
        sectors.append(sector)
    provenance["sector_components"] = {}
    for index in range(12):
        gwa_sector = gwa_by_index[index]
        micro_sector = micro_by_index[index]
        components = {
            "gwa": round(float(gwa_by_index[index].speed_factor), 4),
            "microscale": round(float(micro_by_index[index].speed_factor), 4),
            "gwa_saturated": bool(gwa_sector.saturated),
            "microscale_saturated": bool(micro_sector.saturated),
        }
        for attribute in ("upwind_z0", "downwind_z0", "fetch_m"):
            value = getattr(micro_sector, attribute, None)
            if value is not None:
                components[attribute] = round(float(value), 5)
        provenance["sector_components"][str(index)] = components
    return CombinedSectorResult(STATUS_OK, sectors, provenance)
