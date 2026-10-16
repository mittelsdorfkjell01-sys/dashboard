"""Serve manifests and samples strictly from the active field publication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from collections import OrderedDict
import threading

import numpy as np
from sqlalchemy import func, select

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldModel,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.spatial_fields.contracts_v2 import FieldManifestV2
from app.spatial_fields.publication import active_publication_state
from app.spatial_fields.sampling import temporal_uv, wind_sample
from app.spatial_fields.storage import FieldObjectStorage
from app.spatial_fields.tile_codec import decode_field_tile


class FieldSampleUnavailable(LookupError):
    pass


@dataclass(frozen=True)
class ActiveManifest:
    publication_id: str
    generation: int
    object_key: str
    sha256: str
    manifest: FieldManifestV2


_MANIFEST_CACHE_MAX = 64
_manifest_cache: OrderedDict[str, FieldManifestV2] = OrderedDict()
_manifest_cache_lock = threading.Lock()


def _validated_manifest(storage: FieldObjectStorage, object_key: str, sha256: str) -> FieldManifestV2:
    with _manifest_cache_lock:
        cached = _manifest_cache.get(sha256)
        if cached is not None:
            _manifest_cache.move_to_end(sha256)
            return cached
    payload = storage.get(object_key)
    if hashlib.sha256(payload).hexdigest() != sha256:
        raise RuntimeError("active weather-field manifest checksum mismatch")
    parsed = FieldManifestV2.model_validate_json(payload)
    with _manifest_cache_lock:
        _manifest_cache[sha256] = parsed
        _manifest_cache.move_to_end(sha256)
        while len(_manifest_cache) > _MANIFEST_CACHE_MAX:
            _manifest_cache.popitem(last=False)
    return parsed


def load_active_manifest(
    db, *, storage: FieldObjectStorage, scope_key: str
) -> ActiveManifest | None:
    row = db.execute(
        select(WeatherFieldPublication, WeatherFieldAsset)
        .join(
            WeatherFieldAsset,
            WeatherFieldAsset.id == WeatherFieldPublication.manifest_asset_id,
        )
        .where(
            WeatherFieldPublication.scope_key == scope_key,
            WeatherFieldPublication.active.is_(True),
        )
    ).one_or_none()
    if row is None:
        return None
    publication, asset = row
    return ActiveManifest(
        publication_id=str(publication.id),
        generation=int(publication.generation),
        object_key=asset.object_key,
        sha256=asset.sha256,
        manifest=_validated_manifest(storage, asset.object_key, asset.sha256),
    )


def _tile_coordinates(longitude: float, latitude: float, zoom: int) -> tuple[int, int, float, float]:
    tiles = 1 << zoom
    world_x = (longitude + 180.0) / 360.0 * tiles
    latitude = min(85.05112878, max(-85.05112878, latitude))
    world_y = (
        1.0 - math.asinh(math.tan(math.radians(latitude))) / math.pi
    ) / 2.0 * tiles
    tile_x = min(tiles - 1, max(0, int(math.floor(world_x))))
    tile_y = min(tiles - 1, max(0, int(math.floor(world_y))))
    return tile_x, tile_y, world_x - tile_x, world_y - tile_y


def _bilinear(values: np.ndarray, x: float, y: float) -> float | None:
    height, width = values.shape
    x0, y0 = math.floor(x), math.floor(y)
    x1, y1 = x0 + 1, y0 + 1
    if x0 < 0 or y0 < 0 or x1 >= width or y1 >= height:
        return None
    neighbours = np.array(
        [values[y0, x0], values[y0, x1], values[y1, x0], values[y1, x1]]
    )
    if not np.isfinite(neighbours).all():
        return None
    dx, dy = x - x0, y - y0
    bottom = neighbours[0] * (1 - dx) + neighbours[1] * dx
    top = neighbours[2] * (1 - dx) + neighbours[3] * dx
    return float(bottom * (1 - dy) + top * dy)


def _temporal_scalar(name: str, lower: float, upper: float, alpha: float) -> float:
    if name.endswith("_direction"):
        delta = (upper - lower + 180.0) % 360.0 - 180.0
        return (lower + delta * alpha) % 360.0
    return lower + (upper - lower) * alpha


def _sample_asset(
    db,
    *,
    storage: FieldObjectStorage,
    run_id,
    valid_time: datetime,
    longitude: float,
    latitude: float,
    zoom: int | None = None,
    nearest_valid_radius_pixels: int = 0,
):
    if zoom is None:
        zoom = db.scalar(
            select(func.max(WeatherFieldAsset.source_zoom)).where(
                WeatherFieldAsset.run_id == run_id,
                WeatherFieldAsset.asset_type == "tile",
                WeatherFieldAsset.status == "verified",
                WeatherFieldAsset.valid_time == valid_time,
            )
        )
    if zoom is None:
        raise FieldSampleUnavailable("published field has no tile assets")
    tile_x, tile_y, fraction_x, fraction_y = _tile_coordinates(
        longitude, latitude, zoom
    )
    asset = db.scalar(
        select(WeatherFieldAsset).where(
            WeatherFieldAsset.run_id == run_id,
            WeatherFieldAsset.asset_type == "tile",
            WeatherFieldAsset.status == "verified",
            WeatherFieldAsset.valid_time == valid_time,
            WeatherFieldAsset.source_zoom == zoom,
            WeatherFieldAsset.tile_x == tile_x,
            WeatherFieldAsset.tile_y == tile_y,
        )
    )
    if asset is None:
        raise FieldSampleUnavailable("published field tile is unavailable")
    payload = storage.get(asset.object_key)
    if hashlib.sha256(payload).hexdigest() != asset.sha256:
        raise RuntimeError("published field tile checksum mismatch")
    decoded = decode_field_tile(payload, compression=asset.compression)
    overlap = int(decoded.header.get("overlap", 0))
    tile_size = int(decoded.header["width"]) - overlap * 2
    pixel_x = overlap + fraction_x * tile_size - 0.5
    pixel_y = overlap + fraction_y * tile_size - 0.5
    vector_names = (
        ("wave_u", "wave_v")
        if {"wave_u", "wave_v"}.issubset(decoded.arrays)
        else ("wind_u", "wind_v")
    )
    sample_x, sample_y = pixel_x, pixel_y
    u = _bilinear(decoded.arrays[vector_names[0]], sample_x, sample_y)
    v = _bilinear(decoded.arrays[vector_names[1]], sample_x, sample_y)
    interpolation = "bilinear_uv"
    if (u is None or v is None) and nearest_valid_radius_pixels > 0:
        center_x, center_y = round(pixel_x), round(pixel_y)
        candidates: list[tuple[float, int, int]] = []
        for offset_y in range(-nearest_valid_radius_pixels, nearest_valid_radius_pixels + 1):
            for offset_x in range(-nearest_valid_radius_pixels, nearest_valid_radius_pixels + 1):
                x, y = center_x + offset_x, center_y + offset_y
                if not (0 <= x < decoded.header["width"] and 0 <= y < decoded.header["height"]):
                    continue
                if not (
                    np.isfinite(decoded.arrays[vector_names[0]][y, x])
                    and np.isfinite(decoded.arrays[vector_names[1]][y, x])
                ):
                    continue
                candidates.append((offset_x * offset_x + offset_y * offset_y, x, y))
        if candidates:
            _distance, nearest_x, nearest_y = min(candidates)
            sample_x, sample_y = float(nearest_x), float(nearest_y)
            u = float(decoded.arrays[vector_names[0]][nearest_y, nearest_x])
            v = float(decoded.arrays[vector_names[1]][nearest_y, nearest_x])
            interpolation = "nearest_wet_cell"
    if u is None or v is None:
        raise FieldSampleUnavailable("published field has no value at this coordinate")
    nearest = interpolation == "nearest_wet_cell"
    read_value = (
        (lambda values: float(values[int(sample_y), int(sample_x)]) if np.isfinite(values[int(sample_y), int(sample_x)]) else None)
        if nearest
        else (lambda values: _bilinear(values, sample_x, sample_y))
    )
    gust = read_value(decoded.arrays["wind_gust"]) if "wind_gust" in decoded.arrays else None
    scalar_values = {
        name: read_value(values)
        for name, values in decoded.arrays.items()
        if name not in {"wind_u", "wind_v", "wave_u", "wave_v", "wind_gust"}
    }
    return wind_sample(u, v), gust, scalar_values, asset, vector_names, interpolation


def sample_active_field(
    db,
    *,
    storage: FieldObjectStorage,
    scope_key: str,
    latitude: float,
    longitude: float,
    valid_at: datetime,
    model_key: str | None = None,
    nearest_valid_radius_pixels: int = 0,
) -> dict:
    if valid_at.tzinfo is None or valid_at.utcoffset() != timezone.utc.utcoffset(valid_at):
        raise ValueError("valid_at must be timezone-aware UTC")
    row = db.execute(
        select(WeatherFieldPublication, WeatherFieldRun, WeatherFieldModel)
        .join(WeatherFieldRun, WeatherFieldRun.id == WeatherFieldPublication.run_id)
        .join(WeatherFieldModel, WeatherFieldModel.id == WeatherFieldRun.model_id)
        .where(
            WeatherFieldPublication.scope_key == scope_key,
            WeatherFieldPublication.active.is_(True),
        )
    ).one_or_none()
    if row is None:
        raise FieldSampleUnavailable("no active weather-field publication")
    publication, run, model = row
    if model_key is not None and model_key != model.model_key:
        raise FieldSampleUnavailable(
            "requested model is not the active publication model"
        )
    coverage = run.coverage
    if not (
        coverage["west"] <= longitude <= coverage["east"]
        and coverage["south"] <= latitude <= coverage["north"]
    ):
        raise FieldSampleUnavailable("coordinate is outside active field coverage")
    valid_times = sorted(
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        for value in run.valid_times
    )
    if valid_at < valid_times[0] or valid_at > valid_times[-1]:
        raise FieldSampleUnavailable("valid_at is outside the published horizon")
    upper_index = next(
        index for index, value in enumerate(valid_times) if value >= valid_at
    )
    upper_time = valid_times[upper_index]
    if upper_time == valid_at:
        sample, gust, scalar_values, asset, vector_names, spatial_interpolation = _sample_asset(
            db,
            storage=storage,
            run_id=run.id,
            valid_time=upper_time,
            longitude=longitude,
            latitude=latitude,
            nearest_valid_radius_pixels=nearest_valid_radius_pixels,
        )
        interpolation = spatial_interpolation
        asset_ids = [str(asset.id)]
    else:
        lower_time = valid_times[upper_index - 1]
        lower, lower_gust, lower_scalars, lower_asset, lower_vector_names, lower_interpolation = _sample_asset(
            db,
            storage=storage,
            run_id=run.id,
            valid_time=lower_time,
            longitude=longitude,
            latitude=latitude,
            nearest_valid_radius_pixels=nearest_valid_radius_pixels,
        )
        upper, upper_gust, upper_scalars, upper_asset, upper_vector_names, upper_interpolation = _sample_asset(
            db,
            storage=storage,
            run_id=run.id,
            valid_time=upper_time,
            longitude=longitude,
            latitude=latitude,
            nearest_valid_radius_pixels=nearest_valid_radius_pixels,
        )
        sample = temporal_uv(
            lower,
            upper,
            lower_time=lower_time,
            upper_time=upper_time,
            target_time=valid_at,
        )
        if lower_vector_names != upper_vector_names:
            raise FieldSampleUnavailable("published field vector contract changed within one run")
        vector_names = lower_vector_names
        alpha = (valid_at - lower_time).total_seconds() / (
            upper_time - lower_time
        ).total_seconds()
        gust = (
            lower_gust + (upper_gust - lower_gust) * alpha
            if lower_gust is not None and upper_gust is not None
            else None
        )
        scalar_values = {
            name: _temporal_scalar(name, lower_value, upper_scalars[name], alpha)
            for name, lower_value in lower_scalars.items()
            if lower_value is not None
            and name in upper_scalars
            and upper_scalars[name] is not None
        }
        interpolation = f"{lower_interpolation}+{upper_interpolation}+linear_uv"
        asset_ids = [str(lower_asset.id), str(upper_asset.id)]
    freshness = active_publication_state(db, scope_key)
    common = {
        "publication_id": str(publication.id),
        "generation": publication.generation,
        "run_id": str(run.id),
        "provider": model.provider_key,
        "model": model.model_key,
        "model_run": run.model_run_at,
        "valid_at": valid_at,
        "latitude": latitude,
        "longitude": longitude,
        "interpolation": interpolation,
        "asset_ids": asset_ids,
        "freshness": freshness.freshness if freshness else "expired",
    }
    if vector_names == ("wave_u", "wave_v"):
        return {
            **common,
            "product": "model_wave",
            "wave_u": sample.u_ms,
            "wave_v": sample.v_ms,
            "total_wave_height_m": scalar_values.get("total_wave_height", sample.speed_ms),
            "total_wave_direction_from_deg": sample.direction_from_deg,
            "total_wave_period_s": scalar_values.get("total_wave_period"),
            "wind_sea_height_m": scalar_values.get("wind_sea_height"),
            "wind_sea_direction_from_deg": scalar_values.get("wind_sea_direction"),
            "wind_sea_period_s": scalar_values.get("wind_sea_period"),
            "primary_swell_height_m": scalar_values.get("primary_swell_height"),
            "primary_swell_direction_from_deg": scalar_values.get("primary_swell_direction"),
            "primary_swell_period_s": scalar_values.get("primary_swell_period"),
        }
    return {
        **common,
        "product": "model_wind",
        "u_ms": sample.u_ms,
        "v_ms": sample.v_ms,
        "speed_ms": sample.speed_ms,
        "direction_from_deg": sample.direction_from_deg,
        "gust_ms": gust,
        "temperature_c": scalar_values.get("temperature_2m"),
        "precipitation_mm": scalar_values.get("precipitation"),
        "pressure_hpa": scalar_values.get("pressure_msl"),
        "cloud_cover_percent": scalar_values.get("cloud_cover"),
    }


def sample_active_field_series(
    db,
    *,
    storage: FieldObjectStorage,
    scope_key: str,
    latitude: float,
    longitude: float,
    valid_times,
    model_key: str | None = None,
    nearest_valid_radius_pixels: int = 0,
) -> list[dict]:
    """Sample one point across many valid times from the active publication.

    Each sample reuses :func:`sample_active_field`; times whose asset is missing or
    that fall outside the published horizon are skipped rather than failing the whole
    series, so the point forecast strip degrades gracefully. Storage/health failures
    (``OSError``/``RuntimeError``) still propagate to the caller.
    """
    samples: list[dict] = []
    for valid_at in valid_times:
        try:
            samples.append(
                sample_active_field(
                    db,
                    storage=storage,
                    scope_key=scope_key,
                    latitude=latitude,
                    longitude=longitude,
                    valid_at=valid_at,
                    model_key=model_key,
                    nearest_valid_radius_pixels=nearest_valid_radius_pixels,
                )
            )
        except (FieldSampleUnavailable, ValueError):
            continue
    return samples
