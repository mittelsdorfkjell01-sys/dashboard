"""Bounded Phase-2 weather-field processing and publication candidate pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import uuid

import numpy as np

from app.models.weather_field import WeatherFieldModel, WeatherFieldRun
from app.spatial_fields.contracts_v2 import (
    CLOUD_COVER_SCALE_PERCENT_V2,
    FIELD_TILE_OVERLAP_V2,
    FIELD_TILE_SIZE_V2,
    PRECIPITATION_SCALE_MM_V2,
    PRESSURE_SCALE_HPA_V2,
    TEMPERATURE_SCALE_C_V2,
    WAVE_DIRECTION_SCALE_DEG_V2,
    WAVE_HEIGHT_SCALE_M_V2,
    WAVE_PERIOD_SCALE_S_V2,
    WIND_COMPONENT_SCALE_MS_V2,
    FieldManifestV2,
    classify_freshness,
)
from app.spatial_fields.control_plane import (
    finalize_run_quality,
    record_quality_gate,
    register_asset,
    transition_run,
)
from app.spatial_fields.phase0 import (
    project_xyz_tile,
    xyz_pixel_lonlat,
    xyz_tiles_for_bounds,
)
from app.spatial_fields.providers import (
    FieldSourceSlice,
    DwdWaveFieldProvider,
    GfsFieldProvider,
    IconD2FieldProvider,
    IconEuFieldProvider,
    NoaaGfsWaveProvider,
    WeatherFieldProvider,
)
from app.spatial_fields.publication import (
    PublicationNotReady,
    activate_publication,
    stage_publication,
)
from app.spatial_fields.sampling import bilinear_uv
from app.spatial_fields.scopes import model_scope
from app.spatial_fields.series_codec import FieldSeriesBuilder
from app.spatial_fields.storage import FieldObjectStorage
from app.spatial_fields.tile_codec import (
    TileVariable,
    decode_field_tile,
    encode_field_tile,
    sha256_hex,
)


SOURCE_LODS = (4, 5)
COMPONENT_LIMIT_MS = 100.0
GUST_LIMIT_MS = 150.0
GRIB_TILE_TOLERANCE_MS = 0.25
BORDER_TOLERANCE_MS = 0.051

SCALAR_VARIABLES = {
    "temperature_2m": {
        "unit": "°C",
        "semantic": "air_temperature",
        "height_m": 2.0,
        "scale": TEMPERATURE_SCALE_C_V2,
        "range": (-100.0, 70.0),
    },
    "precipitation": {
        "unit": "mm",
        "semantic": "accumulation",
        "height_m": None,
        "scale": PRECIPITATION_SCALE_MM_V2,
        "range": (0.0, 500.0),
    },
    "pressure_msl": {
        "unit": "hPa",
        "semantic": "mean_sea_level_pressure",
        "height_m": None,
        "scale": PRESSURE_SCALE_HPA_V2,
        "range": (850.0, 1100.0),
    },
    "cloud_cover": {
        "unit": "%",
        "semantic": "fraction",
        "height_m": None,
        "scale": CLOUD_COVER_SCALE_PERCENT_V2,
        "range": (0.0, 100.0),
    },
    "total_wave_height": {"unit": "m", "semantic": "wave_height", "height_m": None, "scale": WAVE_HEIGHT_SCALE_M_V2, "range": (0.0, 40.0)},
    "total_wave_direction": {"unit": "°", "semantic": "direction_from", "height_m": None, "scale": WAVE_DIRECTION_SCALE_DEG_V2, "range": (0.0, 360.0)},
    "total_wave_period": {"unit": "s", "semantic": "wave_period", "height_m": None, "scale": WAVE_PERIOD_SCALE_S_V2, "range": (0.0, 40.0)},
    "wind_sea_height": {"unit": "m", "semantic": "wave_height", "height_m": None, "scale": WAVE_HEIGHT_SCALE_M_V2, "range": (0.0, 40.0)},
    "wind_sea_direction": {"unit": "°", "semantic": "direction_from", "height_m": None, "scale": WAVE_DIRECTION_SCALE_DEG_V2, "range": (0.0, 360.0)},
    "wind_sea_period": {"unit": "s", "semantic": "wave_period", "height_m": None, "scale": WAVE_PERIOD_SCALE_S_V2, "range": (0.0, 40.0)},
    "primary_swell_height": {"unit": "m", "semantic": "wave_height", "height_m": None, "scale": WAVE_HEIGHT_SCALE_M_V2, "range": (0.0, 40.0)},
    "primary_swell_direction": {"unit": "°", "semantic": "direction_from", "height_m": None, "scale": WAVE_DIRECTION_SCALE_DEG_V2, "range": (0.0, 360.0)},
    "primary_swell_period": {"unit": "s", "semantic": "wave_period", "height_m": None, "scale": WAVE_PERIOD_SCALE_S_V2, "range": (0.0, 40.0)},
}


def _lod_profile(model_key: str) -> tuple[tuple[int, ...], list[dict], float]:
    if model_key == "dwd-ewam":
        return (
            (4, 5),
            [
                {"source_zoom": 4, "consumer_zoom_min": 0, "consumer_zoom_max": 5, "source_decimation": 1},
                {"source_zoom": 5, "consumer_zoom_min": 6, "consumer_zoom_max": 9, "source_decimation": 1},
            ],
            10.0,
        )
    if model_key == "dwd-gwam":
        return (
            (2, 3),
            [
                {"source_zoom": 2, "consumer_zoom_min": 0, "consumer_zoom_max": 3, "source_decimation": 1},
                {"source_zoom": 3, "consumer_zoom_min": 4, "consumer_zoom_max": 8, "source_decimation": 1},
            ],
            40.0,
        )
    if model_key == "noaa-gfs-wave":
        return (
            (2, 3),
            [
                {"source_zoom": 2, "consumer_zoom_min": 0, "consumer_zoom_max": 3, "source_decimation": 1},
                {"source_zoom": 3, "consumer_zoom_min": 4, "consumer_zoom_max": 8, "source_decimation": 1},
            ],
            40.0,
        )
    if model_key == "icon-d2":
        return (
            (5, 6),
            [
                {"source_zoom": 5, "consumer_zoom_min": 0, "consumer_zoom_max": 5, "source_decimation": 1},
                {"source_zoom": 6, "consumer_zoom_min": 6, "consumer_zoom_max": 10, "source_decimation": 1},
            ],
            5.0,
        )
    if model_key == "gfs-0p25":
        return (
            (2, 3),
            [
                {"source_zoom": 2, "consumer_zoom_min": 0, "consumer_zoom_max": 3, "source_decimation": 1},
                {"source_zoom": 3, "consumer_zoom_min": 4, "consumer_zoom_max": 8, "source_decimation": 1},
            ],
            40.0,
        )
    return (
        SOURCE_LODS,
        [
            {"source_zoom": 4, "consumer_zoom_min": 0, "consumer_zoom_max": 5, "source_decimation": 1},
            {"source_zoom": 5, "consumer_zoom_min": 6, "consumer_zoom_max": 8, "source_decimation": 1},
        ],
        10.0,
    )


def provider_for_model(model_key: str, *, settings) -> WeatherFieldProvider:
    options = {
        "timeout": settings.weather_field_request_timeout_seconds,
        "max_source_bytes": settings.weather_field_max_source_bytes,
    }
    if model_key == "icon-eu":
        return IconEuFieldProvider(**options)
    if model_key == "icon-d2":
        return IconD2FieldProvider(**options)
    if model_key == "gfs-0p25":
        return GfsFieldProvider(**options)
    if model_key in {"dwd-ewam", "dwd-gwam"}:
        return DwdWaveFieldProvider(model_key, **options)
    if model_key == "noaa-gfs-wave":
        return NoaaGfsWaveProvider(**options)
    raise ValueError(f"unsupported weather-field model: {model_key}")


def _utc_key(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%HZ")


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _tile_center_error(
    source: FieldSourceSlice,
    arrays: dict[str, np.ndarray],
    *,
    z: int,
    x: int,
    y: int,
) -> float | None:
    center = FIELD_TILE_OVERLAP_V2 + FIELD_TILE_SIZE_V2 // 2
    longitude, latitude = xyz_pixel_lonlat(
        z,
        x,
        y,
        pixel_x=center - FIELD_TILE_OVERLAP_V2 + 0.5,
        pixel_y=center - FIELD_TILE_OVERLAP_V2 + 0.5,
        tile_size=FIELD_TILE_SIZE_V2,
    )
    native = bilinear_uv(
        source.u.longitudes,
        source.u.latitudes,
        source.u.values,
        source.v.values,
        longitude=longitude,
        latitude=latitude,
    )
    if native is None:
        return None
    tiled_u = arrays[source.vector_u_name][center, center]
    tiled_v = arrays[source.vector_v_name][center, center]
    if not np.isfinite(tiled_u) or not np.isfinite(tiled_v):
        return None
    return max(abs(float(tiled_u) - native.u_ms), abs(float(tiled_v) - native.v_ms))


def _border_error(
    tiles: dict[tuple[int, int, int], dict[str, np.ndarray]],
) -> float:
    maximum = 0.0
    for (z, x, y), arrays in tiles.items():
        for neighbour_key, left_index, right_index, axis in (
            ((z, x + 1, y), -1, FIELD_TILE_OVERLAP_V2, 1),
            ((z, x, y + 1), -1, FIELD_TILE_OVERLAP_V2, 0),
        ):
            neighbour = tiles.get(neighbour_key)
            if neighbour is None:
                continue
            for name in arrays:
                if name not in arrays or name not in neighbour:
                    continue
                first = np.take(arrays[name], left_index, axis=axis)
                second = np.take(neighbour[name], right_index, axis=axis)
                finite = np.isfinite(first) & np.isfinite(second)
                if finite.any():
                    maximum = max(
                        maximum, float(np.max(np.abs(first[finite] - second[finite])))
                    )
    return maximum


def _manifest(
    *,
    run: WeatherFieldRun,
    model: WeatherFieldModel,
    source: FieldSourceSlice,
    published_at: datetime,
    asset_index_sha256: str,
    root_key: str,
    public_base_url: str,
    publication_id: uuid.UUID,
) -> FieldManifestV2:
    age_seconds = max(0, int((published_at - run.model_run_at).total_seconds()))
    valid_times = [
        datetime.fromisoformat(value.replace("Z", "+00:00")) for value in run.valid_times
    ]
    vector_scale = WAVE_HEIGHT_SCALE_M_V2 if source.product == "wave" else WIND_COMPONENT_SCALE_MS_V2
    variables = [
        {"name": source.vector_u_name, "semantic": "wave_eastward" if source.product == "wave" else "eastward", "unit": "m" if source.product == "wave" else "m/s", "height_m": None if source.product == "wave" else 10.0},
        {"name": source.vector_v_name, "semantic": "wave_northward" if source.product == "wave" else "northward", "unit": "m" if source.product == "wave" else "m/s", "height_m": None if source.product == "wave" else 10.0},
    ]
    quantization = [
        {"variable": source.vector_u_name, "scale": vector_scale},
        {"variable": source.vector_v_name, "scale": vector_scale},
    ]
    if source.gust is not None:
        variables.append({"name": "wind_gust", "semantic": "magnitude", "unit": "m/s", "height_m": 10.0})
        quantization.append(
            {"variable": "wind_gust", "scale": WIND_COMPONENT_SCALE_MS_V2}
        )
    for name, definition in SCALAR_VARIABLES.items():
        if name not in source.scalar_fields:
            continue
        variables.append(
            {
                "name": name,
                "unit": definition["unit"],
                "semantic": definition["semantic"],
                "height_m": definition["height_m"],
            }
        )
        quantization.append({"variable": name, "scale": definition["scale"]})
    resolution = {"icon-d2": 2.2, "icon-eu": 7.0, "dwd-ewam": 5.0}.get(model.model_key, 28.0)
    _source_lods, manifest_lods, display_resolution = _lod_profile(model.model_key)
    return FieldManifestV2.model_validate(
        {
            "publication_id": str(publication_id),
            "provider": model.provider_key,
            "model": model.model_key,
            "model_run": run.model_run_at,
            "published_at": published_at,
            "valid_times": valid_times,
            "coverage": run.coverage,
            "grid": {
                "projection": "regular_ll",
                "grid_type": source.u.definition["gridType"],
                "rows": source.u.values.shape[0],
                "columns": source.u.values.shape[1],
                "longitude_convention": "-180_180",
                "scanning_mode": {
                    key: source.u.definition[key]
                    for key in (
                        "iScansNegatively",
                        "jScansPositively",
                        "jPointsAreConsecutive",
                    )
                },
                "definition": source.u.definition,
                "coordinates_sha256": source.u.coordinate_checksum,
            },
            "native_resolution": {
                "approximate_km": resolution,
                "description": "Derived display metric; native grid is authoritative",
            },
            "display_resolution": {
                "approximate_km": display_resolution,
                "description": "Frozen two-level weather-field-v2 representation",
            },
            "variables": variables,
            "quantization": {"variables": quantization},
            "compression": "gzip",
            "tile_scheme": {
                "tile_size": FIELD_TILE_SIZE_V2,
                "overlap": FIELD_TILE_OVERLAP_V2,
                "lod": manifest_lods,
            },
            "processing_version": run.processing_version,
            # ICON-D2 uses an additive higher-resolution LOD profile. Keep that
            # publication explicitly experimental until a weather-field-v3
            # contract freezes the regional geometry.
            "quality_status": (
                "candidate" if model.model_key == "icon-eu" else "experimental"
            ),
            "freshness": {
                "status": classify_freshness(age_seconds),
                "model_run_at": run.model_run_at,
                "source_discovered_at": run.created_at,
                "processing_started_at": run.started_at,
                "published_at": published_at,
                "expected_next_run_at": run.model_run_at
                + timedelta(hours=model.cadence_hours),
                "age_seconds": age_seconds,
            },
            "attribution": model.attribution,
            "field_template": (
                f"{public_base_url.rstrip('/')}/{root_key}/assets/"
                "{valid_time}/{z}/{x}/{y}.swf2.gz"
            ),
            "series_template": (
                f"{public_base_url.rstrip('/')}/{root_key}/series/"
                "{z}/{x}/{y}.sws1"
            ),
            "checksums": {"asset_index": asset_index_sha256},
        }
    )


def process_run(
    db,
    run_id: uuid.UUID,
    *,
    provider: WeatherFieldProvider,
    storage: FieldObjectStorage,
    settings,
) -> dict:
    run = db.get(WeatherFieldRun, run_id)
    if run is None:
        raise LookupError("weather-field run not found")
    model = db.get(WeatherFieldModel, run.model_id)
    if model is None:
        raise LookupError("weather-field model not found")
    if provider.model_key != model.model_key:
        raise ValueError("provider does not match weather-field run model")
    if run.status != "discovered":
        raise ValueError("only discovered weather-field runs can be processed")

    base_scope = (
        getattr(settings, "wave_field_scope_key", "europe-waves")
        if (model.model_metadata or {}).get("product") == "wave"
        else settings.weather_field_scope_key
    )
    primary_model = (
        getattr(settings, "wave_field_primary_model", "dwd-ewam")
        if (model.model_metadata or {}).get("product") == "wave"
        else getattr(settings, "weather_field_primary_model", "icon-eu")
    )
    root_key = (
        f"{base_scope}/{model.model_key}/"
        f"{run.model_run_at:%Y%m%dT%HZ}/{run.processing_version}"
    )
    expected_hours = [
        int(
            (
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                - run.model_run_at
            ).total_seconds()
            // 3600
        )
        for value in run.valid_times
    ]
    source_lods, _manifest_lods, _display_resolution = _lod_profile(model.model_key)
    transition_run(db, run.id, "downloading")
    db.commit()
    transition_run(db, run.id, "processing")
    db.commit()

    index_entries: list[dict] = []
    downloaded_bytes = 0
    component_min = math.inf
    component_max = -math.inf
    gust_min = math.inf
    gust_max = -math.inf
    scalar_ranges: dict[str, list[float]] = {
        name: [math.inf, -math.inf] for name in SCALAR_VARIABLES
    }
    max_grib_tile_error = 0.0
    max_border_error = 0.0
    coordinate_checksums: set[str] = set()
    source_urls: list[str] = []
    first_source: FieldSourceSlice | None = None
    processed_hours: list[int] = []
    integrity_ok = True
    series_builder = FieldSeriesBuilder()
    series_entries: list[dict] = []

    try:
        for forecast_hour in expected_hours:
            source = provider.fetch(run.model_run_at, forecast_hour)
            if first_source is None:
                first_source = source
                run.native_grid = {
                    "definition": source.u.definition,
                    "coordinates_sha256": source.u.coordinate_checksum,
                    "rows": source.u.values.shape[0],
                    "columns": source.u.values.shape[1],
                }
            downloaded_bytes += source.downloaded_bytes
            if downloaded_bytes > settings.weather_field_max_run_download_bytes:
                raise ValueError("weather-field run exceeded its download byte budget")
            source_urls.extend(source.source_urls)
            coordinate_checksums.add(source.u.coordinate_checksum)
            if source.product == "wind" and source.gust is None:
                raise ValueError("weather-field source is missing wind gust")

            for component in (source.u.values, source.v.values):
                finite = component[np.isfinite(component)]
                if finite.size:
                    component_min = min(component_min, float(finite.min()))
                    component_max = max(component_max, float(finite.max()))
            if source.gust is not None:
                finite_gust = source.gust.values[np.isfinite(source.gust.values)]
                if finite_gust.size:
                    gust_min = min(gust_min, float(finite_gust.min()))
                    gust_max = max(gust_max, float(finite_gust.max()))
            for name, grid in source.scalar_fields.items():
                finite = grid.values[np.isfinite(grid.values)]
                if finite.size and name in scalar_ranges:
                    scalar_ranges[name][0] = min(scalar_ranges[name][0], float(finite.min()))
                    scalar_ranges[name][1] = max(scalar_ranges[name][1], float(finite.max()))

            vector_scale = WAVE_HEIGHT_SCALE_M_V2 if source.product == "wave" else WIND_COMPONENT_SCALE_MS_V2
            variables = (
                TileVariable(source.vector_u_name, scale=vector_scale),
                TileVariable(source.vector_v_name, scale=vector_scale),
            ) + ((TileVariable("wind_gust"),) if source.gust is not None else ()) + tuple(
                TileVariable(name, scale=float(SCALAR_VARIABLES[name]["scale"]))
                for name in SCALAR_VARIABLES
                if name in source.scalar_fields
            )

            time_tiles: dict[tuple[int, int, int], dict[str, np.ndarray]] = {}
            valid_key = _utc_key(source.valid_time)
            for zoom in source_lods:
                for z, x, y in xyz_tiles_for_bounds(
                    run.coverage["west"],
                    run.coverage["south"],
                    run.coverage["east"],
                    run.coverage["north"],
                    zoom,
                ):
                    arrays = {
                        source.vector_u_name: project_xyz_tile(
                            source.u,
                            z=z,
                            x=x,
                            y=y,
                            tile_size=FIELD_TILE_SIZE_V2,
                            overlap=FIELD_TILE_OVERLAP_V2,
                        ),
                        source.vector_v_name: project_xyz_tile(
                            source.v,
                            z=z,
                            x=x,
                            y=y,
                            tile_size=FIELD_TILE_SIZE_V2,
                            overlap=FIELD_TILE_OVERLAP_V2,
                        ),
                        **(
                            {
                                "wind_gust": project_xyz_tile(
                                    source.gust,
                                    z=z,
                                    x=x,
                                    y=y,
                                    tile_size=FIELD_TILE_SIZE_V2,
                                    overlap=FIELD_TILE_OVERLAP_V2,
                                )
                            }
                            if source.gust is not None
                            else {}
                        ),
                        **{
                            name: project_xyz_tile(
                                grid,
                                z=z,
                                x=x,
                                y=y,
                                tile_size=FIELD_TILE_SIZE_V2,
                                overlap=FIELD_TILE_OVERLAP_V2,
                            )
                            for name, grid in source.scalar_fields.items()
                        },
                    }
                    time_tiles[(z, x, y)] = arrays
                    object_key = f"{root_key}/assets/{valid_key}/{z}/{x}/{y}.swf2.gz"
                    payload = encode_field_tile(
                        arrays,
                        metadata={
                            "valid_time": source.valid_time.isoformat().replace(
                                "+00:00", "Z"
                            ),
                            "z": z,
                            "x": x,
                            "y": y,
                            "overlap": FIELD_TILE_OVERLAP_V2,
                        },
                        variables=variables,
                        compression="gzip",
                    )
                    stored = storage.put_immutable(object_key, payload)
                    series_builder.append(
                        z=z,
                        x=x,
                        y=y,
                        valid_time=valid_key,
                        payload=payload,
                    )
                    integrity_ok = integrity_ok and (
                        sha256_hex(storage.get(object_key)) == stored.sha256
                    )
                    register_asset(
                        db,
                        run_id=run.id,
                        asset_type="tile",
                        object_key=object_key,
                        valid_time=source.valid_time,
                        source_zoom=z,
                        tile_x=x,
                        tile_y=y,
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                        content_type="application/vnd.surfwinddata.field-tile",
                        compression="gzip",
                        status="verified",
                    )
                    decoded = decode_field_tile(payload, compression="gzip")
                    error = _tile_center_error(
                        source, decoded.arrays, z=z, x=x, y=y
                    )
                    if error is not None:
                        max_grib_tile_error = max(max_grib_tile_error, error)
                    index_entries.append(
                        {
                            "path": object_key,
                            "valid_time": valid_key,
                            "z": z,
                            "x": x,
                            "y": y,
                            "bytes": stored.size_bytes,
                            "sha256": stored.sha256,
                        }
                    )
            max_border_error = max(max_border_error, _border_error(time_tiles))
            processed_hours.append(forecast_hour)
            run.bytes_downloaded = downloaded_bytes
            db.commit()

        if first_source is None:
            raise ValueError("weather-field run has no source timesteps")
        for (z, x, y), payload in series_builder.containers():
            object_key = f"{root_key}/series/{z}/{x}/{y}.sws1"
            stored = storage.put_immutable(object_key, payload)
            integrity_ok = integrity_ok and (
                sha256_hex(storage.get(object_key)) == stored.sha256
            )
            register_asset(
                db,
                run_id=run.id,
                asset_type="series_tile",
                object_key=object_key,
                source_zoom=z,
                tile_x=x,
                tile_y=y,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                content_type="application/vnd.surfwinddata.field-series",
                compression="none",
                status="verified",
            )
            series_entries.append(
                {
                    "path": object_key,
                    "z": z,
                    "x": x,
                    "y": y,
                    "bytes": stored.size_bytes,
                    "sha256": stored.sha256,
                    "asset_type": "series_tile",
                }
            )
        all_index_entries = [*index_entries, *series_entries]
        index_payload = _canonical_json({"assets": all_index_entries})
        index_key = f"{root_key}/asset-index.json"
        stored_index = storage.put_immutable(index_key, index_payload)
        register_asset(
            db,
            run_id=run.id,
            asset_type="asset_index",
            object_key=index_key,
            size_bytes=stored_index.size_bytes,
            sha256=stored_index.sha256,
            content_type="application/json",
            compression="none",
            status="verified",
        )
        published_at = datetime.now(timezone.utc)
        publication_id = uuid.uuid4()
        manifest = _manifest(
            run=run,
            model=model,
            source=first_source,
            published_at=published_at,
            asset_index_sha256=stored_index.sha256,
            root_key=root_key,
            public_base_url=settings.weather_field_public_base_url,
            publication_id=publication_id,
        )
        manifest_payload = manifest.model_dump_json(indent=2).encode("utf-8")
        manifest_key = f"{root_key}/manifest.json"
        stored_manifest = storage.put_immutable(manifest_key, manifest_payload)
        manifest_asset = register_asset(
            db,
            run_id=run.id,
            asset_type="manifest",
            object_key=manifest_key,
            size_bytes=stored_manifest.size_bytes,
            sha256=stored_manifest.sha256,
            content_type="application/json",
            compression="none",
            status="verified",
        )

        transition_run(db, run.id, "quality_pending")
        longitude_step = (
            float(np.max(np.abs(np.diff(source.u.longitudes))))
            if source.u.longitudes.size > 1
            else 0.0
        )
        latitude_step = (
            float(np.max(np.abs(np.diff(source.u.latitudes))))
            if source.u.latitudes.size > 1
            else 0.0
        )
        gates = {
            "uv_pair": True,
            "utc_times": processed_hours == expected_hours,
            "coverage": all(
                (
                    source.u.longitudes[0]
                    <= run.coverage["west"] + longitude_step,
                    source.u.longitudes[-1]
                    >= run.coverage["east"] - longitude_step,
                    source.u.latitudes[0]
                    <= run.coverage["south"] + latitude_step,
                    source.u.latitudes[-1]
                    >= run.coverage["north"] - latitude_step,
                )
            ),
            "grid_continuity": len(coordinate_checksums) == 1,
            "value_ranges": (
                component_min >= -COMPONENT_LIMIT_MS
                and component_max <= COMPONENT_LIMIT_MS
                and (
                    source.product == "wave"
                    or (gust_min >= 0 and gust_max <= GUST_LIMIT_MS)
                )
                and all(
                    scalar_ranges[name][0] >= float(definition["range"][0])
                    and scalar_ranges[name][1] <= float(definition["range"][1])
                    for name, definition in SCALAR_VARIABLES.items()
                    if scalar_ranges[name][0] != math.inf
                )
            ),
            "asset_integrity": integrity_ok,
            "grib_tile_comparison": max_grib_tile_error
            <= GRIB_TILE_TOLERANCE_MS,
            "tile_border_continuity": max_border_error <= BORDER_TOLERANCE_MS,
            "processing_version": bool(run.processing_version),
            "attribution": bool(model.attribution),
            "near_term_completeness": processed_hours == expected_hours,
        }
        measured_scalar_ranges = {
            name: values
            for name, values in scalar_ranges.items()
            if values[0] != math.inf and values[1] != -math.inf
        }
        metrics = {
            "value_ranges": {
                "component_min_ms": component_min,
                "component_max_ms": component_max,
                "gust_min_ms": None if first_source.product == "wave" else gust_min,
                "gust_max_ms": None if first_source.product == "wave" else gust_max,
                "scalars": measured_scalar_ranges,
            },
            "grib_tile_comparison": {
                "max_component_error_ms": max_grib_tile_error,
                "tolerance_ms": GRIB_TILE_TOLERANCE_MS,
            },
            "tile_border_continuity": {
                "max_component_error_ms": max_border_error,
                "tolerance_ms": BORDER_TOLERANCE_MS,
            },
            "near_term_completeness": {
                "expected_hours": expected_hours,
                "processed_hours": processed_hours,
            },
        }
        for gate_key, passed in gates.items():
            record_quality_gate(
                db,
                run_id=run.id,
                gate_key=gate_key,
                passed=passed,
                metrics=metrics.get(gate_key, {}),
            )
        run.diagnostics = {
            "source_urls": source_urls,
            "tile_count": len(index_entries),
            "series_tile_count": len(series_entries),
            "asset_bytes": sum(item["bytes"] for item in all_index_entries),
            "quality": metrics,
        }
        finalize_run_quality(db, run.id, completed_at=published_at)
        publication = stage_publication(
            db,
                scope_key=model_scope(
                    base_scope,
                    model.model_key,
                    primary_model=primary_model,
                ),
            run_id=run.id,
            manifest_asset_id=manifest_asset.id,
            publication_id=publication_id,
            actor="weather-field-worker",
            reason="phase2-shadow-candidate",
        )
        if run.status != "ready":
            publication.status = "rejected"
        activation_blockers: list[str] = []
        if run.status == "ready" and settings.weather_field_auto_activate:
            try:
                activate_publication(
                    db,
                    publication.id,
                    actor="weather-field-worker",
                    reason="all hard gates and shadow rollout gates passed",
                    # Wind uses the existing station/shadow evidence rollout.
                    # Wave fields have no equivalent observation network yet;
                    # their GRIB, range, continuity and integrity gates remain mandatory.
                    rollout_policy=None if first_source.product == "wave" else settings,
                )
            except PublicationNotReady as exc:
                activation_blockers = list(exc.reasons)
        db.commit()
        return {
            "run_id": str(run.id),
            "run_status": run.status,
            "publication_id": str(publication.id),
            "publication_status": publication.status,
            "tile_count": len(index_entries),
            "series_tile_count": len(series_entries),
            "asset_bytes": sum(item["bytes"] for item in all_index_entries),
            "downloaded_bytes": downloaded_bytes,
            "quality": gates,
            "public_effect": "field-publication" if publication.active else "none",
            "activation_blockers": activation_blockers,
        }
    except Exception as exc:
        db.rollback()
        failed = db.get(WeatherFieldRun, run_id)
        if failed is not None and failed.status not in {"ready", "expired"}:
            failed.status = "failed"
            failed.completed_at = datetime.now(timezone.utc)
            failed.error = f"{type(exc).__name__}: {exc}"[:4000]
            db.commit()
        raise
    finally:
        series_builder.close()
