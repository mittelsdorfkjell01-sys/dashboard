"""Select one fail-closed database shard for the Europe wind campaign."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from app.weather.europe_campaign import load_campaign


SHARD_FILE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "europe-wind-measurement-shards.json"
)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("shard timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class MeasurementShard:
    number: int
    neon_project_id: str
    starts_at: datetime
    ends_at: datetime
    database_id: str

    @property
    def secret_name(self) -> str:
        return f"EUROPE_WIND_MEASUREMENT_DATABASE_URL_SHARD_{self.number}"

    def contains(self, instant: datetime) -> bool:
        return self.starts_at <= instant < self.ends_at


def load_shards(path: Path = SHARD_FILE) -> tuple[MeasurementShard, ...]:
    campaign = load_campaign()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("campaign_id") != campaign.campaign_id:
        raise ValueError("measurement shard campaign mismatch")
    shards = tuple(
        MeasurementShard(
            number=int(item["number"]),
            neon_project_id=str(item["neon_project_id"]),
            starts_at=_utc(item["starts_at"]),
            ends_at=_utc(item["ends_at"]),
            database_id=str(item["database_id"]),
        )
        for item in payload.get("shards", [])
    )
    if len(shards) != 5 or [item.number for item in shards] != [1, 2, 3, 4, 5]:
        raise ValueError("measurement campaign requires exactly five ordered shards")
    if shards[0].starts_at != campaign.starts_at or shards[-1].ends_at != campaign.ends_at:
        raise ValueError("measurement shards must cover the complete campaign")
    for left, right in zip(shards, shards[1:]):
        if left.ends_at != right.starts_at:
            raise ValueError("measurement shards must be contiguous")
    for shard in shards:
        if shard.ends_at <= shard.starts_at:
            raise ValueError("measurement shard end must be after start")
        if not shard.database_id.startswith("surfwind_measurement_"):
            raise ValueError("measurement shard database must be dedicated")
        if not shard.neon_project_id or shard.neon_project_id == "rough-dawn-52880495":
            raise ValueError("measurement shard must use a dedicated Neon project")
    if len({item.neon_project_id for item in shards}) != len(shards):
        raise ValueError("measurement shards must use distinct Neon projects")
    return shards


def select_shard(
    *,
    now: datetime | None = None,
    number: int | None = None,
) -> MeasurementShard:
    shards = load_shards()
    if number is not None:
        return shards[number - 1] if 1 <= number <= len(shards) else _invalid_shard()
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for shard in shards:
        if shard.contains(instant):
            return shard
    raise ValueError("no measurement shard is active at this time")


def _invalid_shard() -> MeasurementShard:
    raise ValueError("measurement shard number must be between 1 and 5")


def configure_github_environment(
    shard: MeasurementShard,
    environ: dict[str, str],
) -> dict[str, object]:
    database_url = environ.get(shard.secret_name, "").strip()
    if not database_url:
        raise ValueError(f"missing measurement database secret for shard {shard.number}")
    actual_database = make_url(database_url).database or ""
    if actual_database != shard.database_id:
        raise ValueError("measurement shard database identity mismatch")
    github_env = environ.get("GITHUB_ENV", "").strip()
    if not github_env:
        raise ValueError("GITHUB_ENV is required")
    with Path(github_env).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"DATABASE_URL={database_url}\n")
        handle.write(
            "EUROPE_WIND_MEASUREMENT_DATABASE_ID="
            f"{shard.database_id}\n"
        )
        handle.write(f"EUROPE_WIND_MEASUREMENT_SHARD={shard.number}\n")
    return {
        "status": "configured",
        "shard": shard.number,
        "database_id": shard.database_id,
        "neon_project_id": shard.neon_project_id,
        "starts_at": shard.starts_at.isoformat(),
        "ends_at": shard.ends_at.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int)
    parser.add_argument("--github-env", action="store_true")
    args = parser.parse_args()
    shard = select_shard(number=args.shard)
    if args.github_env:
        report = configure_github_environment(shard, dict(os.environ))
    else:
        report = {
            "shard": shard.number,
            "database_id": shard.database_id,
            "neon_project_id": shard.neon_project_id,
            "starts_at": shard.starts_at.isoformat(),
            "ends_at": shard.ends_at.isoformat(),
        }
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
