from app.weather.catalog import (
    AIFS,
    AROME_AT,
    AROME_FR,
    DMI_EU,
    ICON_2I,
    ICON_CH1,
    ICON_D2,
    ICON_EU,
    KNMI_NL,
    UKMO_2KM,
    forecast_models,
)
from app.weather.contracts import ModelFamily
from app.weather.weights import normalized_model_weights

# Sub-3 km models: attaching any one means the spot is no longer global-only.
SUB_3KM = {AROME_FR.id, ICON_D2.id, ICON_CH1.id, "meteoswiss_icon_ch2", AROME_AT.id, ICON_2I.id, UKMO_2KM.id,
           KNMI_NL.id, "knmi_harmonie_arome_europe", DMI_EU.id}


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


def test_atlantic_france_gets_a_sub_3km_model():
    # Hossegor: AROME France HD (~1.5 km), verified to return data on Open-Meteo.
    ids = _ids(43.66, -1.44)
    assert AROME_FR.id in ids
    assert SUB_3KM.intersection(ids)


def test_alps_get_meteoswiss_and_austria_models():
    assert ICON_CH1.id in _ids(46.8, 8.2)
    assert AROME_AT.id in _ids(47.5, 14.0)


def test_italy_gets_icon_2i():
    assert ICON_2I.id in _ids(39.2, 9.1)  # Sardinia


def test_uk_gets_ukmo_2km():
    assert UKMO_2KM.id in _ids(50.4, -5.0)  # Cornwall


def test_southern_spain_gets_a_regional_fallback_but_no_sub_3km():
    # Honest limitation: no sub-3 km Open-Meteo model covers Tarifa (36 N); it
    # still gains a ~7 km regional instead of being global-only.
    ids = _ids(36.01, -5.60)
    assert ICON_EU.id in ids
    assert AROME_FR.id not in ids
    assert not SUB_3KM.intersection(ids)


def test_regional_members_are_deduplicated():
    ids = _ids(46.8, 8.2)  # Alpine overlap of several domains
    assert len(ids) == len(set(ids))


def test_weight_normalization_is_stable_with_multiple_regionals():
    globals_ = [("ecmwf_ifs", ModelFamily.IFS), ("ncep_gfs_global", ModelFamily.GFS),
                ("ecmwf_aifs025_single", ModelFamily.AIFS)]
    for count in (2, 3, 5):
        regionals = [(f"r{i}", ModelFamily.REGIONAL) for i in range(count)]
        weights = normalized_model_weights(regionals + globals_, lead_hours=24)
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        regional_total = sum(weights[f"r{i}"] for i in range(count))
        assert abs(regional_total - 0.50) < 1e-9  # family total independent of member count
        # Members inside the family share equally.
        assert len({round(weights[f"r{i}"], 9) for i in range(count)}) == 1
        assert abs(weights["ecmwf_ifs"] - 0.25) < 1e-9  # a global is unaffected by regional count
