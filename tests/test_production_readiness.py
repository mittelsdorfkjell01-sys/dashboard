from scripts import production_readiness


def test_wave_api_smoke_checks_ten_day_chain_manifest_and_series(monkeypatch):
    requested = []

    def get_json(_base_url, path):
        requested.append(path)
        if path == "/weather-fields/waves/health":
            return {
                "status": "ok",
                "primary": {"active_publication": {"publication_id": "ewam"}},
                "fallback": {"active_publication": {"publication_id": "gwam"}},
                "extended": {"active_publication": {"publication_id": "gfs-wave"}},
            }
        if "valid_at=2026-10-20" in path:
            return {"selection": {"selected_model": "noaa-gfs-wave"}}
        if path.startswith("/weather-fields/waves?"):
            return {
                "publication_id": "ewam",
                "manifest": {"valid_times": ["2026-10-10T12:00:00Z"]},
            }
        if path.startswith("/weather-fields/waves/sample?"):
            return {"total_wave_height_m": 1.7}
        if path.startswith("/weather-fields/waves/sample/series?"):
            return {
                "samples": [
                    {"valid_at": "2026-10-10T12:00:00Z"},
                    {"valid_at": "2026-10-20T12:00:00Z"},
                ],
                "sources": [
                    {
                        "model": "noaa-gfs-wave",
                        "model_run": "2026-10-10T12:00:00Z",
                        "valid_to": "2026-10-20T12:00:00Z",
                    }
                ],
            }
        raise AssertionError(path)

    monkeypatch.setattr(production_readiness, "_get_json", get_json)

    production_readiness.wave_api_smoke("https://surfwinddata.example")

    assert requested[0] == "/weather-fields/waves/health"
    assert "lat=54.4" in requested[1]
    assert "valid_at=2026-10-10T12%3A00%3A00Z" in requested[2]
    assert "/sample/series?" in requested[3]
    assert "valid_at=2026-10-20T12%3A00%3A00Z" in requested[4]
