from types import SimpleNamespace
import uuid

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon

from app.admin.duplicates import (
    DuplicateResult,
    ExactDuplicateError,
    LikelyDuplicateError,
    enforce_duplicates,
    find_region_duplicates,
    find_spot_duplicates,
)
from app.admin.constants import validate_styles
from app.names import normalize_name


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Db:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _statement):
        return _Rows(self._rows)


def _point(lat: float, lon: float):
    return from_shape(Point(lon, lat), srid=4326)


def test_spot_classifier_separates_exact_and_near_similar_candidates():
    region_id = uuid.uuid4()
    exact = SimpleNamespace(
        id=uuid.uuid4(), name="Kühlungsborn", normalized_name=normalize_name("Kühlungsborn"),
        region_id=region_id, location=_point(54.15, 11.75),
    )
    similar = SimpleNamespace(
        id=uuid.uuid4(), name="Kühlungsborn West", normalized_name=normalize_name("Kühlungsborn West"),
        region_id=uuid.uuid4(), location=_point(54.151, 11.751),
    )
    result = find_spot_duplicates(
        _Db([(exact, "Ostsee", 1.0), (similar, "Ostsee West", 0.76)]),
        name=" kuhlungsborn ",
        region_id=region_id,
        lat=54.15,
        lon=11.75,
    )
    assert [item["id"] for item in result.exact] == [str(exact.id)]
    assert [item["id"] for item in result.likely] == [str(similar.id)]
    assert result.likely[0]["distance_m"] < 200


def test_region_classifier_uses_country_without_coordinates_and_bounds_when_present():
    candidate = SimpleNamespace(
        id=uuid.uuid4(), name="Costa Nord", normalized_name=normalize_name("Costa Nord"),
        country="IT", center=None, bounds=None,
    )
    without_coordinates = find_region_duplicates(
        _Db([(candidate, 0.86)]),
        name="Costa Norte",
        country="it",
        lat=None,
        lon=None,
    )
    assert without_coordinates.likely[0]["distance_m"] is None

    polygon = from_shape(
        Polygon([(8, 40), (10, 40), (10, 42), (8, 42), (8, 40)]), srid=4326
    )
    candidate.bounds = polygon
    overlap = find_region_duplicates(
        _Db([(candidate, 0.65)]),
        name="Costa North",
        country="FR",
        lat=None,
        lon=None,
        bounds=polygon,
    )
    assert overlap.likely[0]["bounds_overlap"] is True


def test_duplicate_enforcement_never_overrides_exact_and_requires_explicit_likely_flag():
    exact = DuplicateResult(exact=[{"id": "exact"}], likely=[])
    with pytest.raises(ExactDuplicateError):
        enforce_duplicates("Spot", exact, allow_likely=True)

    likely = DuplicateResult(exact=[], likely=[{"id": "likely"}])
    with pytest.raises(LikelyDuplicateError):
        enforce_duplicates("Region", likely, allow_likely=False)
    assert enforce_duplicates("Region", likely, allow_likely=True) == [{"id": "likely"}]


def test_wavekite_is_an_independent_supported_riding_style():
    assert validate_styles(["wave_riding", "wavekite"]) == ["wave_riding", "wavekite"]
