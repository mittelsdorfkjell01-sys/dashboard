"""Version-2 wind availability climatology, independent from legacy scoring."""

from app.wind_climatology.aggregate import ALGORITHM_VERSION, WIND_WINDOWS, aggregate

__all__ = ["ALGORITHM_VERSION", "WIND_WINDOWS", "aggregate"]
