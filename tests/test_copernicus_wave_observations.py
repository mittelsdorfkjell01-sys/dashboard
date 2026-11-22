from scripts.copernicus_wave_observations import europe_region, normalize_records


def test_normalizes_long_form_and_rejects_bad_variable_qc():
    base = {
        "platform_id": "buoy-1",
        "time": "2026-11-20 12:00:00",
        "latitude": 54.0,
        "longitude": 7.0,
    }
    rows = [
        {**base, "variable": "VHM0", "value": 1.8, "value_qc": 1.0},
        {**base, "variable": "VTM10", "value": 7.2, "value_qc": 2},
        {**base, "variable": "VMDR", "value": 361.0, "value_qc": 4},
    ]

    assert normalize_records(rows) == [
        {
            "platform_id": "buoy-1",
            "platform_name": None,
            "observed_at": "2026-11-20T12:00:00+00:00",
            "latitude": 54.0,
            "longitude": 7.0,
            "location_class": "unknown",
            "significant_height_m": 1.8,
            "period_s": 7.2,
            "period_semantic": "energy_period_tm10",
            "qc_status": "probably_good",
        }
    ]


def test_normalizes_wide_form_with_period_preference_and_direction():
    rows = [
        {
            "platform_id": "buoy-2",
            "time": "2026-11-20T13:00:00Z",
            "latitude": 43.0,
            "longitude": 5.0,
            "VHM0": 0.9,
            "VHM0_QC": 1,
            "VTM10": 5.5,
            "VTM10_QC": 1,
            "VTPK": 8.0,
            "VTPK_QC": 1,
            "VMDR": 370.0,
            "VMDR_QC": 1,
        }
    ]

    observation = normalize_records(rows)[0]
    assert observation["period_s"] == 5.5
    assert observation["period_semantic"] == "energy_period_tm10"
    assert observation["direction_from_deg"] == 10.0
    assert observation["direction_semantic"] == "mean_direction_from"
    assert observation["qc_status"] == "good"


def test_europe_region_classification_is_stable_for_major_basins():
    assert europe_region(34.0, 43.0) == "black-sea"
    assert europe_region(20.0, 58.0) == "baltic"
    assert europe_region(10.0, 38.0) == "mediterranean"
    assert europe_region(4.0, 55.0) == "north-sea"
    assert europe_region(5.0, 68.0) == "arctic-norwegian"
    assert europe_region(-12.0, 48.0) == "atlantic-ibi"
