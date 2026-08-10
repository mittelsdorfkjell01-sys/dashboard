"""Canonical wind-speed units and lossless boundary conversions."""

from __future__ import annotations

from enum import StrEnum


class WindSpeedUnit(StrEnum):
    METRES_PER_SECOND = "m/s"
    KNOTS = "kn"
    KILOMETRES_PER_HOUR = "km/h"


_TO_METRES_PER_SECOND = {
    WindSpeedUnit.METRES_PER_SECOND: 1.0,
    WindSpeedUnit.KNOTS: 0.5144444444444445,
    WindSpeedUnit.KILOMETRES_PER_HOUR: 1.0 / 3.6,
}


def convert_wind_speed(
    value: float,
    source: WindSpeedUnit,
    target: WindSpeedUnit,
) -> float:
    """Convert a wind speed without display rounding.

    Rounding is deliberately left to the presentation layer so repeated unit
    changes never alter the underlying forecast value.
    """
    return float(value) * _TO_METRES_PER_SECOND[source] / _TO_METRES_PER_SECOND[target]
