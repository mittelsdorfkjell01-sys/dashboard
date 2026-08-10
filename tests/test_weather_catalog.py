from app.weather.catalog import AIFS, DMI_EU, ICON_D2, KNMI_NL, forecast_models


def _ids(lat, lon):
    return [model.id for model in forecast_models(lat, lon)]


def test_germany_gets_icon_regional_and_aifs():
    ids = _ids(54.5, 10.0)
    assert ICON_D2.id in ids
    assert AIFS.id in ids


def test_netherlands_gets_knmi_inset():
    assert KNMI_NL.id in _ids(52.3, 4.8)


def test_denmark_gets_dmi_regional():
    assert DMI_EU.id in _ids(56.0, 10.0)


def test_catalog_contains_no_seamless_blend():
    assert all("seamless" not in model_id for model_id in _ids(54.5, 10.0))
