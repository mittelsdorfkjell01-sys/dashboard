from datetime import datetime, timedelta, timezone

import pytest

from app.weather.europe_campaign import load_campaign
from scripts.europe_measurement_shards import (
    configure_github_environment,
    load_shards,
    select_shard,
)


def test_five_shards_cover_campaign_without_gaps_or_overlap():
    campaign = load_campaign()
    shards = load_shards()

    assert len(shards) == 5
    assert shards[0].starts_at == campaign.starts_at
    assert shards[-1].ends_at == campaign.ends_at
    assert all(left.ends_at == right.starts_at for left, right in zip(shards, shards[1:]))
    assert all(shard.ends_at - shard.starts_at <= timedelta(days=4, hours=7) for shard in shards)
    assert len({shard.neon_project_id for shard in shards}) == 5
    assert "rough-dawn-52880495" not in {shard.neon_project_id for shard in shards}


def test_shard_selection_changes_exactly_at_boundary():
    shards = load_shards()
    boundary = shards[0].ends_at

    assert select_shard(now=boundary - timedelta(microseconds=1)).number == 1
    assert select_shard(now=boundary).number == 2


def test_github_environment_configuration_is_identity_checked(tmp_path):
    github_env = tmp_path / "github-env"
    shard = select_shard(number=3)
    secret = "postgresql+psycopg://user:secret@example.invalid/surfwind_measurement_202611_v2_s3"

    report = configure_github_environment(shard, {
        "GITHUB_ENV": str(github_env),
        shard.secret_name: secret,
    })

    configured = github_env.read_text(encoding="utf-8")
    assert f"DATABASE_URL={secret}" in configured
    assert f"EUROPE_WIND_MEASUREMENT_DATABASE_ID={shard.database_id}" in configured
    assert report["shard"] == 3


def test_github_environment_rejects_wrong_database_identity(tmp_path):
    shard = select_shard(number=2)
    with pytest.raises(ValueError, match="identity mismatch"):
        configure_github_environment(shard, {
            "GITHUB_ENV": str(tmp_path / "github-env"),
            shard.secret_name: "postgresql://user:secret@example.invalid/production",
        })


def test_selection_fails_outside_campaign_window():
    campaign = load_campaign()
    with pytest.raises(ValueError, match="no measurement shard"):
        select_shard(now=campaign.ends_at.astimezone(timezone.utc))
