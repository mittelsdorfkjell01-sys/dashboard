"""No-data-before-gate planning for official CDSE Copernicus DEM assets."""

from __future__ import annotations
from dataclasses import dataclass
from app.config import get_settings


@dataclass(frozen=True)
class GateResult:
    status: str
    assets: tuple[dict, ...]
    estimated_bytes: int
    reason: str | None = None


def preflight_gate(
    planned_assets: list[dict],
    *,
    credentials: tuple[str | None, str | None] | None = None,
) -> GateResult:
    settings = get_settings()
    credentials = credentials or (
        settings.copernicus_cdse_client_id,
        settings.copernicus_cdse_client_secret,
    )
    if not all(credentials):
        return GateResult(
            "blocked_credentials", (), 0, "CDSE CCM credentials are not configured"
        )
    if len(planned_assets) > 200:
        return GateResult("blocked_budget", (), 0, "request count exceeds 200")
    total = 0
    for asset in planned_assets:
        if asset.get("product_instance") not in {
            "COP-DEM_GLO-30-DGED",
            "COP-DEM_GLO-90-DGED",
        }:
            return GateResult("blocked_license", (), 0, "unapproved product instance")
        size = asset.get("size_bytes")
        if size is None:
            return GateResult("blocked_budget", (), 0, "asset size is unknown")
        if size > settings.geodata_phase2_max_asset_bytes:
            return GateResult("blocked_budget", (), 0, "single asset limit exceeded")
        total += size
    if total > settings.geodata_phase2_max_run_bytes:
        return GateResult("blocked_budget", (), total, "run byte limit exceeded")
    return GateResult("ready", tuple(planned_assets), total)
