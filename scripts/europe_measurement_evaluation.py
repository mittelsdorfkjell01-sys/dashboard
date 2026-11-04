"""Aggregate the five read-only Europe measurement database shards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy.engine import make_url

from app.weather.europe_campaign import load_campaign
from scripts.europe_measurement_shards import MeasurementShard, load_shards


def _sum_mapping(reports: list[dict], key: str) -> dict[str, int]:
    totals: dict[str, int] = {}
    for report in reports:
        for name, count in (report.get(key) or {}).items():
            totals[name] = totals.get(name, 0) + int(count or 0)
    return totals


def _latest(reports: list[dict], key: str) -> str | None:
    values = [report.get(key) for report in reports if report.get(key)]
    return max(values) if values else None


def aggregate_shard_reports(
    shard_reports: list[dict],
    *,
    now: datetime | None = None,
) -> dict:
    """Combine already collected shard counters without opening a database."""
    campaign = load_campaign()
    shards = load_shards()
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    databases = [item["database"] for item in shard_reports]
    cycle_totals = _sum_mapping(databases, "campaign_cycles")
    expected_due = 0
    per_shard = []
    for shard, item in zip(shards, shard_reports, strict=True):
        due_end = min(max(instant, shard.starts_at), shard.ends_at)
        expected = int(
            (due_end - shard.starts_at).total_seconds()
            // (campaign.expected_interval_minutes * 60)
        )
        cycles = item["database"].get("campaign_cycles") or {}
        usable = int(cycles.get("success", 0)) + int(cycles.get("partial", 0))
        expected_due += expected
        per_shard.append({
            "number": shard.number,
            "neon_project_id": shard.neon_project_id,
            "database_id": shard.database_id,
            "starts_at": shard.starts_at.isoformat(),
            "ends_at": shard.ends_at.isoformat(),
            "expected_cycles_due": expected,
            "usable_cycles": usable,
            "capture_ratio_due": round(usable / max(1, expected), 4),
            "database": item["database"],
        })

    usable_total = int(cycle_totals.get("success", 0)) + int(
        cycle_totals.get("partial", 0)
    )
    activation_eligible = sum(
        int(report.get("activation_eligible_residuals", 0)) for report in databases
    )
    shards_with_data = sum(
        1 for report in databases if (report.get("campaign_cycles") or {})
    )
    phase = campaign.phase(instant)
    return {
        "campaign_id": campaign.campaign_id,
        "generated_at": instant.isoformat(),
        "phase": phase,
        "public_effect": "none",
        "shard_count": len(shards),
        "shards_with_data": shards_with_data,
        "expected_cycles_due": expected_due,
        "usable_cycles": usable_total,
        "capture_ratio_due": round(usable_total / max(1, expected_due), 4),
        "campaign_cycles": cycle_totals,
        "observations": sum(int(item.get("observations", 0)) for item in databases),
        "operational_observations": sum(
            int(item.get("operational_observations", 0)) for item in databases
        ),
        "exact_bundles": sum(int(item.get("exact_bundles", 0)) for item in databases),
        "residuals": _sum_mapping(databases, "residuals"),
        "activation_eligible_residuals": activation_eligible,
        "database_size_bytes": sum(
            int(item.get("database_size_bytes", 0)) for item in databases
        ),
        "latest_observation_at": _latest(databases, "latest_observation_at"),
        "latest_campaign_cycle_finished_at": _latest(
            databases, "latest_campaign_cycle_finished_at"
        ),
        "evaluation_ready": (
            phase == "ended"
            and shards_with_data == len(shards)
            and activation_eligible == 0
        ),
        "shards": per_shard,
    }


def collect_shard_report(shard: MeasurementShard, environ: dict[str, str]) -> dict:
    """Run the existing status reader in an isolated process for one shard."""
    database_url = environ.get(shard.secret_name, "").strip()
    if not database_url:
        raise ValueError(f"missing database secret for shard {shard.number}")
    if (make_url(database_url).database or "") != shard.database_id:
        raise ValueError(f"database identity mismatch for shard {shard.number}")
    child_env = dict(environ)
    child_env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "scripts.europe_measurement_status", "--database"],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
        env=child_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"read-only status failed for shard {shard.number}")
    payload = json.loads(result.stdout)
    return {"number": shard.number, "database": payload["database"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    shard_reports = [
        collect_shard_report(shard, dict(os.environ)) for shard in load_shards()
    ]
    report = aggregate_shard_reports(shard_reports)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
