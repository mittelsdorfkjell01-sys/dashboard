"""Pure phase-4 verification math; never feeds public model weights."""

from __future__ import annotations
import math
from app.weather.vectors import uv_to_wind, wind_to_uv

LEAD_BANDS = ((0, 24), (25, 48), (49, 72), (73, 120), (121, 240))


def lead_band(hours: int) -> str | None:
    return next(
        (f"{low}-{high}h" for low, high in LEAD_BANDS if low <= hours <= high), None
    )


def circular_error(forecast: float, observed: float) -> float:
    return abs((forecast - observed + 180) % 360 - 180)


def aggregate_observations(rows: list[dict]) -> dict | None:
    valid = [
        r
        for r in rows
        if r.get("quality_status") == "valid" and r.get("wind_speed_ms") is not None
    ]
    if not valid:
        return None
    vectors = [
        wind_to_uv(float(r["wind_speed_ms"]), float(r["wind_direction_deg"]))
        for r in valid
        if r.get("wind_direction_deg") is not None
    ]
    if vectors:
        u = sum(x for x, _ in vectors) / len(vectors)
        v = sum(y for _, y in vectors) / len(vectors)
        speed, direction = uv_to_wind(u, v)
    else:
        speed = sum(float(r["wind_speed_ms"]) for r in valid) / len(valid)
        direction = None
        u = v = None
    gusts = [
        float(r["wind_gust_ms"]) for r in valid if r.get("wind_gust_ms") is not None
    ]
    return {
        "sample_count": len(valid),
        "wind_speed_ms": speed,
        "wind_direction_deg": direction,
        "u_ms": u,
        "v_ms": v,
        "wind_gust_ms": max(gusts) if gusts else None,
    }


def verification_metrics(
    pairs: list[tuple[dict, dict]], *, threshold_ms: float = 14 * 0.514444
) -> dict:
    speed = []
    vector = []
    direction = []
    gust = []
    hits = misses = false_alarms = correct_negatives = 0
    for forecast, obs in pairs:
        if forecast.get("wind_speed_ms") is None or obs.get("wind_speed_ms") is None:
            continue
        error = float(forecast["wind_speed_ms"]) - float(obs["wind_speed_ms"])
        speed.append(error)
        if all(x.get(k) is not None for x in (forecast, obs) for k in ("u_ms", "v_ms")):
            vector.append(
                math.hypot(
                    forecast["u_ms"] - obs["u_ms"], forecast["v_ms"] - obs["v_ms"]
                )
            )
        if (
            float(obs["wind_speed_ms"]) >= 1.5
            and forecast.get("wind_direction_deg") is not None
            and obs.get("wind_direction_deg") is not None
        ):
            direction.append(
                circular_error(
                    float(forecast["wind_direction_deg"]),
                    float(obs["wind_direction_deg"]),
                )
            )
        if (
            forecast.get("wind_gust_ms") is not None
            and obs.get("wind_gust_ms") is not None
        ):
            gust.append(float(forecast["wind_gust_ms"]) - float(obs["wind_gust_ms"]))
        predicted = float(forecast["wind_speed_ms"]) >= threshold_ms
        actual = float(obs["wind_speed_ms"]) >= threshold_ms
        if predicted and actual:
            hits += 1
        elif predicted:
            false_alarms += 1
        elif actual:
            misses += 1
        else:
            correct_negatives += 1

    def stats(errors):
        return (
            None
            if not errors
            else {
                "bias": sum(errors) / len(errors),
                "mae": sum(abs(x) for x in errors) / len(errors),
                "rmse": math.sqrt(sum(x * x for x in errors) / len(errors)),
                "n": len(errors),
            }
        )

    return {
        "sample_count": len(speed),
        "speed": stats(speed),
        "vector_mae": sum(vector) / len(vector) if vector else None,
        "vector_n": len(vector),
        "direction_mae_deg": sum(direction) / len(direction) if direction else None,
        "direction_n": len(direction),
        "gust": stats(gust),
        "event_14kn": {
            "hits": hits,
            "false_alarms": false_alarms,
            "misses": misses,
            "correct_negatives": correct_negatives,
            "n": len(speed),
        },
    }
