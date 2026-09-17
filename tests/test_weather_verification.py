import io
import zipfile

from app.weather.providers.dwd import parse_now_zip
from app.weather.verification import MIN_CALIBRATION_SAMPLES, calibration_stats, lead_bucket


def test_lead_buckets_are_stable():
    assert [lead_bucket(value) for value in (0, 48, 49, 120, 121, 240)] == [
        "0-48h", "0-48h", "49-120h", "49-120h", "121-240h", "121-240h"
    ]


def test_calibration_requires_enough_samples_and_uses_robust_medians():
    assert calibration_stats([1.0] * (MIN_CALIBRATION_SAMPLES - 1)) is None
    stats = calibration_stats([1.0] * MIN_CALIBRATION_SAMPLES + [50.0], peer_mae=2.0)
    assert stats is not None
    assert stats.bias_ms == 1.0
    assert stats.mae_ms == 1.0
    assert stats.weight_multiplier == 2.0


def test_dwd_zip_parser_retains_missing_values_as_rejected():
    csv = (
        "STATIONS_ID;MESS_DATUM;QN;FF_10;DD_10;eor\n"
        "123;202608101200;3;7.4;245;eor\n"
        "123;202608101210;3;-999;-999;eor\n"
    )
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("produkt_zehn_min_ff_20260810_20260810_00123.txt", csv)
    rows = parse_now_zip(payload.getvalue())
    assert len(rows) == 2
    assert rows[0].wind_speed_ms == 7.4
    assert rows[0].wind_direction_deg == 245
    assert rows[0].import_status == "accepted"
    assert rows[1].wind_speed_ms is None
    assert rows[1].wind_direction_deg is None
    assert rows[1].import_status == "rejected"
    assert rows[1].rejection_reason == "wind_speed:invalid"
    assert rows[1].raw_payload["FF_10"] == "-999"
