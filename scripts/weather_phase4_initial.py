"""One bounded, idempotent initial phase-4 shadow collection cycle."""

from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal
from app.forecast.contracts import ProviderRequest
from app.forecast.providers import NoaaGfsProvider
from app.models import (
    ForecastSnapshot,
    Spot,
    SpotGeoShadowProfile,
    WeatherShadowForecast,
    WeatherShadowRun,
)
from app.weather.shadow_study import (
    CONSENSUS_VERSION,
    GEO_CANDIDATE_VERSION,
    NORMALIZER_VERSION,
    STUDY_VERSION,
    get_or_create_study,
    store_forecast,
)
from app.weather.units import WindSpeedUnit, convert_wind_speed
from app.weather.vectors import wind_to_uv

NAMES = ("Baleal", "Brouwersdam", "Mundaka", "Lo Stagnone", "Pozo Izquierdo")
HOURS = tuple(range(0, 241, 12))
MAX_BYTES = 50_000_000
MAX_REQUESTS = 200


class CountingClient:
    def __init__(self):
        self.inner = httpx.Client()
        self.requests = 0
        self.bytes = 0

    def get(self, *args, **kwargs):
        if self.requests >= MAX_REQUESTS:
            raise RuntimeError("provider request budget exceeded")
        response = self.inner.get(*args, **kwargs)
        self.requests += 1
        self.bytes += len(response.content)
        if self.bytes > MAX_BYTES:
            raise RuntimeError("provider byte budget exceeded")
        return response


def snapshot_hashes(db):
    from scripts.geodata_phase3_backfill import public_baseline

    return public_baseline(db)


def latest_safe_run(now):
    floored = now.replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=now.hour % 6
    )
    return floored - timedelta(hours=6)


def versions(profile):
    return {
        "study": STUDY_VERSION,
        "normalizer": NORMALIZER_VERSION,
        "consensus": CONSENSUS_VERSION,
        "geo_candidate": GEO_CANDIDATE_VERSION,
        "geo_profile_id": str(profile.id),
        "geo_profile_input_hash": profile.input_hash,
        "geo_profile_algorithm": profile.algorithm_version,
        "geo_profile_class": profile.profile_class,
    }


def main(*, model_run_override: datetime | None = None):
    started = datetime.now(timezone.utc)
    model_run = model_run_override or latest_safe_run(started)
    if model_run.tzinfo is None:
        model_run = model_run.replace(tzinfo=timezone.utc)
    else:
        model_run = model_run.astimezone(timezone.utc)
    run_key = f"{STUDY_VERSION}:gfs-0p25:{model_run.isoformat()}"
    with SessionLocal() as db:
        before = snapshot_hashes(db)
        study = get_or_create_study(db)
        existing = db.scalar(
            select(WeatherShadowRun).where(WeatherShadowRun.run_key == run_key)
        )
        if existing:
            points = db.scalar(
                select(func.count())
                .select_from(WeatherShadowForecast)
                .where(WeatherShadowForecast.run_id == existing.id)
            )
            result = {
                "status": existing.status,
                "deduplicated": True,
                "network_requests": 0,
                "network_bytes": 0,
                "forecast_points": points,
                "run_id": str(existing.id),
            }
            print(json.dumps(result))
            db.rollback()
            return result
        run = WeatherShadowRun(
            study_id=study.id,
            run_key=run_key,
            issued_at=started,
            status="processing",
            diagnostics={
                "dry_run": {
                    "gfs_requests": len(NAMES) * len(HOURS),
                    "probe_bytes": 909,
                    "projected_bytes": 909 * len(NAMES) * len(HOURS),
                    "limit_bytes": MAX_BYTES,
                },
                "icon_eu": "blocked_provider_budget",
            },
            started_at=started,
        )
        db.add(run)
        db.flush()
        spots = {
            s.name: s
            for s in db.scalars(
                select(Spot).where(Spot.name.in_(NAMES), Spot.status == "published")
            ).all()
        }
        profiles = {
            p.spot_id: p
            for p in db.scalars(
                select(SpotGeoShadowProfile).where(
                    SpotGeoShadowProfile.spot_id.in_([s.id for s in spots.values()]),
                    SpotGeoShadowProfile.active_shadow.is_(True),
                    SpotGeoShadowProfile.profile_class == "A",
                )
            ).all()
        }
        if len(spots) != 5 or len(profiles) != 5:
            raise RuntimeError("five bound class-A profiles required")
        counter = CountingClient()
        provider = NoaaGfsProvider(client=counter, timeout=30)
        created = 0
        per_spot = {}
        for name in NAMES:
            spot = spots[name]
            profile = profiles[spot.id]
            point = to_shape(spot.location)
            values = provider.fetch(
                ProviderRequest(
                    latitude=point.y,
                    longitude=point.x,
                    model="gfs-0p25",
                    run_at=model_run,
                    forecast_hours=HOURS,
                )
            )
            counts = {
                "gfs_raw": 0,
                "consensus_uncorrected": 0,
                "consensus_geo_candidate": 0,
                "public_baseline": 0,
                "open_meteo_baseline": 0,
                "icon_eu_raw": 0,
            }
            for value in values:
                base = {
                    "run_id": run.id,
                    "spot_id": spot.id,
                    "shadow_profile_id": profile.id,
                    "model_run_at": value.model_run,
                    "retrieved_at": value.fetched_at,
                    "valid_at": value.valid_at,
                    "lead_hours": value.horizon_hours,
                    "wind_speed_ms": value.speed_ms,
                    "wind_gust_ms": value.gust_ms,
                    "wind_direction_deg": value.direction_deg,
                    "u_ms": value.u_ms,
                    "v_ms": value.v_ms,
                    "versions": versions(profile),
                    "provenance": {
                        "source": value.source_key,
                        "dataset_version": value.dataset_version,
                        "grid": {
                            "latitude": value.grid_point.latitude,
                            "longitude": value.grid_point.longitude,
                            "distance_km": value.grid_point.distance_km,
                            "resolution_km": value.horizontal_resolution_km,
                        },
                    },
                }
                for variant, model in (
                    ("gfs_raw", "gfs-0p25"),
                    ("consensus_uncorrected", "gfs-0p25-only"),
                    ("consensus_geo_candidate", "gfs-0p25-only-no-effect"),
                ):
                    _, inserted = store_forecast(
                        db, **base, variant=variant, provider_model=model
                    )
                    created += inserted
                    counts[variant] += int(inserted)
            snapshot = db.scalar(
                select(ForecastSnapshot).where(
                    ForecastSnapshot.spot_id == spot.id,
                    ForecastSnapshot.active.is_(True),
                )
            )
            if snapshot:
                for day in snapshot.payload.get("days", []):
                    for hour in day.get("hours", []):
                        try:
                            valid = datetime.fromisoformat(hour["time"])
                            speed = convert_wind_speed(
                                float(hour["wind"]),
                                WindSpeedUnit.KNOTS,
                                WindSpeedUnit.METRES_PER_SECOND,
                            )
                            direction = float(hour["dir"]) % 360
                            u, v = wind_to_uv(speed, direction)
                        except (KeyError, TypeError, ValueError):
                            continue
                        lead = max(
                            0,
                            round(
                                (valid - snapshot.generated_at).total_seconds() / 3600
                            ),
                        )
                        if lead > 300:
                            continue
                        _, inserted = store_forecast(
                            db,
                            run_id=run.id,
                            spot_id=spot.id,
                            shadow_profile_id=profile.id,
                            variant="public_baseline",
                            provider_model="surfwinddata-forecast",
                            model_run_at=snapshot.generated_at,
                            retrieved_at=started,
                            valid_at=valid,
                            lead_hours=lead,
                            wind_speed_ms=speed,
                            wind_gust_ms=convert_wind_speed(
                                float(hour["gust"]),
                                WindSpeedUnit.KNOTS,
                                WindSpeedUnit.METRES_PER_SECOND,
                            )
                            if hour.get("gust") is not None
                            else None,
                            wind_direction_deg=direction,
                            u_ms=u,
                            v_ms=v,
                            versions=versions(profile),
                            provenance={
                                "snapshot_id": str(snapshot.id),
                                "as_issued": True,
                            },
                        )
                        created += inserted
                        counts["public_baseline"] += int(inserted)
            per_spot[name] = {
                "variants": counts,
                "gfs_status": "collected",
                "icon_eu_status": "not_covered"
                if name == "Pozo Izquierdo"
                else "blocked_provider_budget",
                "observation_status": "blocked_observation_source",
            }
        run.status = "collecting_with_observation_gaps"
        run.finished_at = datetime.now(timezone.utc)
        run.diagnostics = {
            **run.diagnostics,
            "requests": counter.requests,
            "bytes": counter.bytes,
            "forecast_points_created": created,
            "spots": per_spot,
        }
        study.status = "collecting_with_observation_gaps"
        db.commit()
        run_id = str(run.id)
    with SessionLocal() as db:
        after = snapshot_hashes(db)
        total = db.scalar(
            select(func.count())
            .select_from(WeatherShadowForecast)
            .where(WeatherShadowForecast.run_id == run_id)
        )
    if before != after:
        raise RuntimeError("public baseline changed")
    report = {
        "study_version": STUDY_VERSION,
        "status": "collecting_with_observation_gaps",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "model_runs": {"gfs": model_run.isoformat(), "icon_eu": None},
        "forecast_points": total,
        "created": created,
        "deduplicated": False,
        "provider_requests": counter.requests + 3,
        "provider_bytes": counter.bytes + 1818,
        "preflight_requests": 3,
        "retries": 0,
        "spots": per_spot,
        "observations": 0,
        "public_baseline_identical": True,
        "blocked_components": {
            "icon_eu": "blocked_provider_budget",
            "observations": "blocked_observation_source",
        },
        "scheduler": {"required_frequency_hours": 6, "external_action_required": True},
    }
    Path("reports/geodata-phase4-initial-cycle.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    Path("reports/geodata-phase4-initial-cycle.md").write_text(
        f"# Phase-4 initial cycle\n\nStatus: `collecting_with_observation_gaps`. {total} immutable forecast points stored. Public baseline unchanged.\n",
        encoding="utf-8",
    )
    result = {
        "status": report["status"],
        "forecast_points": total,
        "requests": report["provider_requests"],
        "bytes": report["provider_bytes"],
        "public_identical": True,
        "run_id": run_id,
    }
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
