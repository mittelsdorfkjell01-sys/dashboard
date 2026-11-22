"""Import quality-controlled Copernicus Marine wave observations for Europe."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from typing import Iterable, Mapping


DATASET_ID = "cmems_obs-ins_glo_phybgcwav_mynrt_na_irr"
SOURCE_REVISION = "copernicus-marine-nrt-v1"
ACCEPTED_QC = frozenset({"1", "2", "good", "probably_good"})
VARIABLES = ("VHM0", "VTM10", "VTM02", "VTPK", "VMDR")


def europe_region(longitude: float, latitude: float) -> str:
    """Return a stable broad European sea region for verification grouping."""

    if 27 <= longitude <= 42 and 40 <= latitude <= 48:
        return "black-sea"
    if 9 <= longitude <= 31 and 53 <= latitude <= 66:
        return "baltic"
    if -6 <= longitude <= 37 and 30 <= latitude <= 46:
        return "mediterranean"
    if -5 <= longitude <= 14 and 48 <= latitude <= 62:
        return "north-sea"
    if latitude >= 62:
        return "arctic-norwegian"
    return "atlantic-ibi"


def _clean(value):
    if value is None:
        return None
    try:
        if math.isnan(value):
            return None
    except TypeError:
        pass
    text = str(value).strip()
    return (
        value
        if text and text.casefold() not in {"nan", "nat", "none", "<na>"}
        else None
    )


def _utc_text(value) -> str:
    text = str(value).strip().replace(" ", "T")
    instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc).isoformat()


def _lookup(row: Mapping, *names: str):
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        value = _clean(lowered.get(name.casefold()))
        if value is not None:
            return value
    return None


def _qc(row: Mapping, variable: str) -> str:
    value = _lookup(
        row,
        f"{variable}_qc",
        f"{variable}_value_qc",
        f"{variable}_quality_control",
        "value_qc",
        "qc",
    )
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value or "").strip().casefold()


def _base(row: Mapping) -> dict | None:
    platform_id = _lookup(row, "platform_id", "platform", "station_id")
    observed_at = _lookup(row, "time", "observed_at", "datetime")
    latitude = _lookup(row, "latitude", "lat")
    longitude = _lookup(row, "longitude", "lon")
    if None in (platform_id, observed_at, latitude, longitude):
        return None
    return {
        "platform_id": str(platform_id),
        "platform_name": _lookup(row, "platform_name", "station_name"),
        "observed_at": _utc_text(observed_at),
        "latitude": float(latitude),
        "longitude": float(longitude),
        "location_class": "unknown",
    }


def _observation(base: dict, values: Mapping[str, tuple[object, str]]) -> dict | None:
    accepted = {
        variable: (float(value), qc)
        for variable, (value, qc) in values.items()
        if _clean(value) is not None and qc in ACCEPTED_QC
    }
    if not accepted:
        return None
    result = dict(base)
    if "VHM0" in accepted:
        result["significant_height_m"] = accepted["VHM0"][0]
    for variable, semantic in (
        ("VTM10", "energy_period_tm10"),
        ("VTM02", "spectral_period_tm02"),
        ("VTPK", "peak_period"),
    ):
        if variable in accepted:
            result["period_s"] = accepted[variable][0]
            result["period_semantic"] = semantic
            break
    if "VMDR" in accepted:
        result["direction_from_deg"] = accepted["VMDR"][0] % 360
        result["direction_semantic"] = "mean_direction_from"
    if not any(
        key in result
        for key in ("significant_height_m", "period_s", "direction_from_deg")
    ):
        return None
    result["qc_status"] = (
        "probably_good"
        if any(qc in {"2", "probably_good"} for _value, qc in accepted.values())
        else "good"
    )
    return result


def normalize_records(records: Iterable[Mapping]) -> list[dict]:
    """Normalize both Copernicus long and wide dataframe layouts."""

    wide_rows: list[dict] = []
    grouped: dict[tuple, dict] = defaultdict(dict)
    bases: dict[tuple, dict] = {}
    for row in records:
        base = _base(row)
        if base is None:
            continue
        variable = str(_lookup(row, "variable") or "").upper()
        if variable in VARIABLES:
            key = (
                base["platform_id"],
                base["observed_at"],
                base["latitude"],
                base["longitude"],
            )
            bases[key] = base
            grouped[key][variable] = (_lookup(row, "value"), _qc(row, variable))
            continue
        values = {
            name: (_lookup(row, name), _qc(row, name)) for name in VARIABLES
        }
        observation = _observation(base, values)
        if observation is not None:
            wide_rows.append(observation)
    long_rows = [
        observation
        for key, values in grouped.items()
        if (observation := _observation(bases[key], values)) is not None
    ]
    return sorted(
        [*wide_rows, *long_rows],
        key=lambda row: (row["platform_id"], row["observed_at"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    now = datetime.now(timezone.utc)
    parser.add_argument("--start", default=(now - timedelta(hours=72)).isoformat())
    parser.add_argument("--end", default=now.isoformat())
    parser.add_argument("--minimum-observations", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    username = os.getenv("COPERNICUS_MARINE_USERNAME") or os.getenv(
        "COPERNICUSMARINE_SERVICE_USERNAME"
    )
    password = os.getenv("COPERNICUS_MARINE_PASSWORD") or os.getenv(
        "COPERNICUSMARINE_SERVICE_PASSWORD"
    )
    if not username or not password:
        raise SystemExit("Copernicus Marine credentials are required")

    import copernicusmarine

    dataframe = copernicusmarine.read_dataframe(
        dataset_id=DATASET_ID,
        dataset_part="latest",
        username=username,
        password=password,
        variables=list(VARIABLES),
        minimum_longitude=-32,
        maximum_longitude=45,
        minimum_latitude=24,
        maximum_latitude=72,
        start_datetime=args.start,
        end_datetime=args.end,
        service="platformseries",
        raise_if_updating=True,
        disable_progress_bar=True,
    )
    records = dataframe.reset_index().to_dict(orient="records")
    observations = normalize_records(records)
    if len(observations) < args.minimum_observations:
        raise SystemExit(
            "insufficient accepted Copernicus wave observations: "
            f"{len(observations)} (required {args.minimum_observations})"
        )

    from app.db.session import SessionLocal
    from app.weather.wave_verification import import_wave_observation_rows

    grouped_rows: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        grouped_rows[europe_region(row["longitude"], row["latitude"])].append(row)
    payload = json.dumps(observations, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    totals = {"accepted": 0, "persisted": 0, "rejected": 0, "platforms": 0}
    with SessionLocal() as db:
        for region_code, rows in sorted(grouped_rows.items()):
            result = import_wave_observation_rows(
                db,
                rows,
                provider_key="copernicus-marine",
                region_code=region_code,
                source_revision=SOURCE_REVISION,
                source_file=DATASET_ID,
                source_sha256=digest,
                dry_run=args.dry_run,
            )
            for key in totals:
                totals[key] += int(result[key])
    print(
        json.dumps(
            {
                **totals,
                "dry_run": args.dry_run,
                "regions": sorted(grouped_rows),
                "source_sha256": digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
