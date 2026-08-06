from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.tides.calculation import CurvePoint


class Fes2022Provider:
    """Thin fail-closed adapter around the official CNES PyFES API."""

    def __init__(self, config_path: str):
        path = Path(config_path)
        if not path.is_file():
            raise RuntimeError("TIDE_PYFES_CONFIG fehlt oder ist nicht lesbar")
        try:
            import pyfes
        except ImportError as exc:
            raise RuntimeError("PyFES ist nur im Tide-Worker zu installieren") from exc
        self._pyfes = pyfes
        self._config = pyfes.config.load(str(path))

    def curve(self, lat: float, lon: float, times: list[datetime]) -> list[CurvePoint]:
        import numpy as np

        dates = np.array([np.datetime64(value.replace(tzinfo=None), "s") for value in times])
        lons = np.full(dates.shape, lon, dtype=float)
        lats = np.full(dates.shape, lat, dtype=float)
        tide, long_period, flags = self._pyfes.evaluate_tide(
            self._config.models["tide"], dates, lons, lats,
            settings=self._config.settings,
        )
        total = tide + long_period
        if np.any(~np.isfinite(total)):
            raise RuntimeError("FES2022b liefert am Modellanker keine vollständige Kurve")
        return [CurvePoint(at, float(height)) for at, height in zip(times, total, strict=True)]
