"""Configuration and deterministic sampling for the Europe shadow campaign."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

from app.weather.providers.common import ObservationStation


CAMPAIGN_FILE = Path(__file__).resolve().parents[2] / "config" / "europe-wind-measurement.json"


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("campaign timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EuropeWindCampaign:
    campaign_id: str
    starts_at: datetime
    ends_at: datetime
    provider: str
    mode: str
    public_effect: str
    station_limit: int
    bounds: tuple[float, float, float, float]
    status: str

    def phase(self, at: datetime | None = None) -> str:
        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if self.status == "cancelled":
            return "cancelled"
        if instant < self.starts_at:
            return "scheduled"
        if instant >= self.ends_at:
            return "ended"
        return "active"


def load_campaign(path: Path = CAMPAIGN_FILE) -> EuropeWindCampaign:
    payload = json.loads(path.read_text(encoding="utf-8"))
    bounds = payload["bounds"]
    starts_at, ends_at = _utc(payload["starts_at"]), _utc(payload["ends_at"])
    if ends_at <= starts_at:
        raise ValueError("campaign end must be after start")
    if ends_at - starts_at != timedelta(days=21):
        raise ValueError("Europe measurement campaign must run exactly 21 days")
    if payload.get("mode") != "shadow" or payload.get("public_effect") != "none":
        raise ValueError("Europe measurement campaign must remain shadow-only")
    return EuropeWindCampaign(
        campaign_id=str(payload["campaign_id"]),
        starts_at=starts_at,
        ends_at=ends_at,
        provider=str(payload["provider"]),
        mode=str(payload["mode"]),
        public_effect=str(payload["public_effect"]),
        station_limit=int(payload["station_limit"]),
        bounds=(
            float(bounds["south"]), float(bounds["north"]),
            float(bounds["west"]), float(bounds["east"]),
        ),
        status=str(payload["status"]),
    )


def select_balanced_stations(
    stations: list[ObservationStation],
    *,
    bounds: tuple[float, float, float, float],
    limit: int,
    cell_degrees: float = 2.0,
) -> list[ObservationStation]:
    """Select a deterministic spatially balanced Europe-wide station subset."""
    south, north, west, east = bounds
    cells: dict[tuple[int, int], list[ObservationStation]] = {}
    for station in stations:
        if not station.active or not (
            south <= station.latitude <= north and west <= station.longitude <= east
        ):
            continue
        key = (
            math.floor((station.latitude - south) / cell_degrees),
            math.floor((station.longitude - west) / cell_degrees),
        )
        cells.setdefault(key, []).append(station)
    for values in cells.values():
        values.sort(key=lambda item: item.station_id)

    selected: list[ObservationStation] = []
    ordered_cells = sorted(cells)
    if len(ordered_cells) > limit:
        # One representative per cell is already too many. Use deterministic
        # farthest-point sampling so truncation cannot silently discard northern
        # or eastern Europe merely because grid keys sort south-west first.
        representatives = [cells[key][0] for key in ordered_cells]
        centre_lat = (south + north) / 2
        centre_lon = (west + east) / 2

        def distance_sq(left: ObservationStation, lat: float, lon: float) -> float:
            lon_scale = max(0.2, math.cos(math.radians((left.latitude + lat) / 2)))
            return (left.latitude - lat) ** 2 + ((left.longitude - lon) * lon_scale) ** 2

        first = min(
            representatives,
            key=lambda item: (distance_sq(item, centre_lat, centre_lon), item.station_id),
        )
        selected = [first]
        remaining = [item for item in representatives if item is not first]
        nearest = {item.station_id: distance_sq(item, first.latitude, first.longitude)
                   for item in remaining}
        while remaining and len(selected) < limit:
            next_station = max(
                remaining, key=lambda item: (nearest[item.station_id], item.station_id)
            )
            selected.append(next_station)
            remaining.remove(next_station)
            for item in remaining:
                nearest[item.station_id] = min(
                    nearest[item.station_id],
                    distance_sq(item, next_station.latitude, next_station.longitude),
                )
        return sorted(selected, key=lambda item: item.station_id)

    depth = 0
    while len(selected) < max(1, limit):
        added = False
        for key in ordered_cells:
            values = cells[key]
            if depth < len(values):
                selected.append(values[depth])
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break
        depth += 1
    return selected
