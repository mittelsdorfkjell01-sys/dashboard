from __future__ import annotations

import argparse
import logging
import uuid
from datetime import datetime, time, timedelta, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select, update

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Spot, TideCalculationRun, TideEvent, TideEventOverride, TideProfile
from app.schemas.common import GeoPoint
from app.tides import ALGORITHM_VERSION
from app.tides.anchor import FesMaskAnchorSelector
from app.tides.calculation import corrected_time, detect_extrema, effective_uncertainty
from app.tides.fes import Fes2022Provider

logger = logging.getLogger(__name__)


class TideWorker:
    def __init__(self):
        settings = get_settings()
        if not all((settings.tide_pyfes_config, settings.tide_mask_file, settings.tide_land_geojson)):
            raise RuntimeError("Tide-Worker ist nicht konfiguriert: PyFES-Konfiguration, FES-Maske und Land-GeoJSON werden benötigt")
        self.settings = settings
        self.provider = Fes2022Provider(settings.tide_pyfes_config)
        self.selector = FesMaskAnchorSelector(settings.tide_mask_file, settings.tide_land_geojson)

    def process_queue(self, *, limit: int | None = None) -> dict:
        self.enqueue_due()
        db = SessionLocal()
        processed = failed = 0
        try:
            runs = list(db.scalars(
                select(TideCalculationRun).where(TideCalculationRun.status == "queued")
                .order_by(TideCalculationRun.created_at).limit(limit or self.settings.tide_batch_size)
            ))
            run_ids = [run.id for run in runs]
        finally:
            db.close()
        for run_id in run_ids:
            try:
                self.process_run(run_id)
                processed += 1
            except Exception:
                failed += 1
                logger.exception("tide run %s failed", run_id)
        return {"processed": processed, "failed": failed}

    def enqueue_due(self) -> int:
        db = SessionLocal()
        try:
            threshold = datetime.now(timezone.utc) - timedelta(
                days=self.settings.tide_horizon_days - self.settings.tide_refresh_before_days
            )
            profiles = list(db.scalars(select(TideProfile).where(
                TideProfile.enabled.is_(True),
                (TideProfile.last_calculated_at.is_(None)) | (TideProfile.last_calculated_at < threshold),
            ).limit(self.settings.tide_batch_size)))
            count = 0
            for profile in profiles:
                existing = db.scalar(select(TideCalculationRun.id).where(
                    TideCalculationRun.spot_id == profile.spot_id,
                    TideCalculationRun.profile_version == profile.version,
                    TideCalculationRun.status.in_(("queued", "running")),
                ).limit(1))
                if existing:
                    continue
                db.add(TideCalculationRun(
                    spot_id=profile.spot_id, status="queued", requested_by="scheduler",
                    model_name=profile.model_name, model_version=profile.model_version,
                    algorithm_version=ALGORITHM_VERSION, profile_version=profile.version,
                    details={"action": "calculate", "reason": "horizon_refresh"},
                ))
                profile.calculation_status = "queued"
                count += 1
            db.commit()
            return count
        finally:
            db.close()

    def process_run(self, run_id: uuid.UUID) -> None:
        db = SessionLocal()
        try:
            run = db.get(TideCalculationRun, run_id)
            if run is None or run.status != "queued":
                return
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            db.commit()
            profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == run.spot_id))
            spot = db.get(Spot, run.spot_id)
            if profile is None or spot is None or not profile.enabled:
                raise RuntimeError("Aktives Tideprofil oder Spot fehlt")
            if run.profile_version != profile.version:
                run.status = "succeeded"
                run.details = {**(run.details or {}), "skipped": "newer_profile_version"}
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
            action = (run.details or {}).get("action", "calculate")
            anchor_changed = action in {"anchor_and_calculate", "validate_anchor_and_calculate"}
            if action == "anchor_and_calculate" or (profile.manual_anchor is None and profile.automatic_anchor is None):
                self._select_anchor(profile, spot)
                anchor_changed = True
            anchor = profile.manual_anchor if profile.manual_anchor is not None else profile.automatic_anchor
            if anchor is None:
                raise RuntimeError("Kein plausibler Modellanker verfügbar")
            anchor_point = GeoPoint.from_geo(anchor)
            valid, extrapolated = self.selector.validate(anchor_point.lat, anchor_point.lon)
            if not valid:
                profile.anchor_status = "invalid"
                profile.quality_status = "unavailable"
                raise RuntimeError("Der Modellanker liegt nicht auf einem gültigen FES-Ozeanpixel")
            if extrapolated and "Modellpunkt liegt im extrapolierten Küstenraster." not in (profile.anchor_warnings or []):
                profile.anchor_warnings = [*(profile.anchor_warnings or []), "Modellpunkt liegt im extrapolierten Küstenraster."]
            if anchor_changed or profile.anchor_status == "needs_review":
                profile.anchor_status = "auto_selected"
                profile.quality_status = "model_only"
                profile.version += 1
                run.profile_version = profile.version
                from app.tides.service import _add_revision

                _add_revision(
                    db, profile, "Modellanker durch Tide-Worker validiert", "tide-worker"
                )
            self._calculate(profile, anchor_point.lat, anchor_point.lon, db=db)
            run.status = "succeeded"
            run.processed_spots = 1
            run.completed_at = datetime.now(timezone.utc)
            profile.calculation_status = "ready"
            profile.calculation_error = None
            profile.last_calculated_at = run.completed_at
            db.commit()
        except Exception as exc:
            db.rollback()
            run = db.get(TideCalculationRun, run_id)
            if run is not None:
                run.status = "failed"
                run.failed_spots = 1
                run.error = str(exc)[:4000]
                run.completed_at = datetime.now(timezone.utc)
                profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == run.spot_id))
                if profile is not None:
                    profile.calculation_status = "failed"
                    profile.calculation_error = str(exc)[:4000]
                db.commit()
            raise
        finally:
            db.close()

    def _select_anchor(self, profile: TideProfile, spot: Spot) -> None:
        point = GeoPoint.from_geo(spot.location)
        candidate = self.selector.select(
            point.lat, point.lon, max_distance_km=self.settings.tide_max_anchor_distance_km
        )
        if candidate is None:
            profile.anchor_status = "invalid"
            profile.anchor_warnings = ["Kein erreichbarer FES-Ozeanpunkt innerhalb der Suchdistanz gefunden."]
            raise RuntimeError(profile.anchor_warnings[0])
        profile.automatic_anchor = WKTElement(f"POINT({candidate.lon} {candidate.lat})", srid=4326)
        profile.anchor_distance_m = candidate.distance_m
        profile.anchor_kind = "extrapolated" if candidate.extrapolated else "native_grid"
        profile.anchor_status = "auto_selected"
        profile.anchor_determined_at = datetime.now(timezone.utc)
        profile.anchor_warnings = list(candidate.warnings)
        profile.quality_status = "model_only"
        if not profile.timezone:
            try:
                from timezonefinder import TimezoneFinder
                profile.timezone = TimezoneFinder(in_memory=True).timezone_at(lat=point.lat, lng=point.lon)
            except ImportError as exc:
                raise RuntimeError("timezonefinder fehlt im Tide-Worker") from exc

    def _calculate(self, profile: TideProfile, lat: float, lon: float, *, db) -> None:
        today = datetime.now(timezone.utc).date()
        # A fixed UTC lattice makes raw extrema reproducible, so overrides keyed
        # by raw time survive later calculations of the overlapping horizon.
        start = datetime.combine(today - timedelta(days=1), time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=self.settings.tide_horizon_days + 2)
        step = timedelta(minutes=self.settings.tide_sample_minutes)
        times, cursor = [], start
        while cursor <= end:
            times.append(cursor)
            cursor += step
        raw_events = detect_extrema(self.provider.curve(lat, lon, times))
        if len(raw_events) < self.settings.tide_horizon_days * 2:
            raise RuntimeError("FES-Kurve enthält zu wenige stabile Hoch-/Niedrigwasserereignisse")
        overrides = list(db.scalars(select(TideEventOverride).where(
            TideEventOverride.spot_id == profile.spot_id,
            TideEventOverride.active.is_(True), TideEventOverride.scope == "single",
        )))
        calculated_at = datetime.now(timezone.utc)
        uncertainty = effective_uncertainty(
            manual=profile.manual_uncertainty_minutes,
            estimated=profile.estimated_uncertainty_minutes,
            quality=profile.quality_status,
        )
        new_events = []
        for raw in raw_events:
            adjusted = corrected_time(
                raw.time, raw.event_type,
                global_offset_minutes=profile.global_offset_minutes,
                high_offset_minutes=profile.high_offset_minutes,
                low_offset_minutes=profile.low_offset_minutes,
            )
            override = next((item for item in overrides if item.event_type == raw.event_type and item.raw_time == raw.time), None)
            if override:
                adjusted = override.manual_time
            new_events.append(TideEvent(
                spot_id=profile.spot_id, profile_version=profile.version,
                cycle_key=f"{raw.event_type}:{raw.time.isoformat()}", event_type=raw.event_type,
                raw_time=raw.time, corrected_time=adjusted, relative_height=raw.relative_height,
                uncertainty_minutes=uncertainty, calculated_at=calculated_at,
                model_name=profile.model_name, model_version=profile.model_version,
            ))
        # Replacement is part of the same transaction. Old valid generations
        # remain untouched if calculation or insertion fails.
        db.execute(delete(TideEvent).where(
            TideEvent.spot_id == profile.spot_id,
            TideEvent.profile_version == profile.version,
        ))
        db.add_all(new_events)
        db.flush()
        db.execute(update(TideEvent).where(
            TideEvent.spot_id == profile.spot_id,
            TideEvent.profile_version != profile.version,
            TideEvent.status == "valid",
        ).values(status="superseded"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Surfwinddata tide jobs")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    outcome = TideWorker().process_queue(limit=args.limit)
    logger.info("tide worker finished: %s", outcome)
    if outcome["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
