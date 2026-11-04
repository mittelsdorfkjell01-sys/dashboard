from app.weather.europe_campaign import load_campaign
from scripts.europe_measurement_evaluation import aggregate_shard_reports


def _report(number: int) -> dict:
    return {
        "number": number,
        "database": {
            "stations": 64,
            "observations": number * 10,
            "operational_observations": number * 4,
            "exact_bundles": number * 3,
            "residuals": {"degraded": number},
            "activation_eligible_residuals": 0,
            "database_size_bytes": number * 1000,
            "latest_observation_at": f"2026-11-{number + 10:02d}T00:00:00+00:00",
            "latest_campaign_cycle_finished_at": (
                f"2026-11-{number + 10:02d}T00:05:00+00:00"
            ),
            "campaign_cycles": {"success": number, "partial": 1},
        },
    }


def test_evaluation_aggregates_all_shards_without_writing():
    campaign = load_campaign()
    report = aggregate_shard_reports(
        [_report(number) for number in range(1, 6)],
        now=campaign.ends_at,
    )

    assert report["phase"] == "ended"
    assert report["shard_count"] == 5
    assert report["shards_with_data"] == 5
    assert report["observations"] == 150
    assert report["operational_observations"] == 60
    assert report["exact_bundles"] == 45
    assert report["residuals"] == {"degraded": 15}
    assert report["campaign_cycles"] == {"success": 15, "partial": 5}
    assert report["usable_cycles"] == 20
    assert report["expected_cycles_due"] == 21 * 48
    assert report["activation_eligible_residuals"] == 0
    assert report["evaluation_ready"] is True


def test_evaluation_only_counts_intervals_due_at_report_time():
    campaign = load_campaign()
    report = aggregate_shard_reports(
        [_report(number) for number in range(1, 6)],
        now=campaign.starts_at,
    )

    assert report["phase"] == "active"
    assert report["expected_cycles_due"] == 0
    assert report["evaluation_ready"] is False
