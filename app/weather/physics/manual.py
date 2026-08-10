from __future__ import annotations


def direction_in_sector(direction: float, start: float, end: float) -> bool:
    direction %= 360.0
    if start <= end:
        return start <= direction <= end
    return direction >= start or direction <= end


def select_sector(direction: float, sectors) -> object | None:
    """Use only an enabled sector from the latest reviewed profile version."""
    eligible = [
        sector for sector in sectors
        if sector.enabled and direction_in_sector(direction, sector.start_deg, sector.end_deg)
    ]
    return max(eligible, key=lambda sector: sector.version) if eligible else None
