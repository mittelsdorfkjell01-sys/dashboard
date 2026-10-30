"""Read-only summary of weather/backtest GitHub Actions.

The command never starts, cancels or reruns a workflow. It uses the already
authenticated GitHub CLI and prints only workflow state and public run URLs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


WORKFLOWS = (
    "europe-wind-measurement.yml",
    "europe-wind-measurement-monitor.yml",
    "tide-worker.yml",
    "weather-verification.yml",
    "weather-shadow.yml",
    "live-wind-shadow.yml",
)


def workflow_status(workflow: str) -> dict[str, str | None]:
    result = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            workflow,
            "--limit",
            "1",
            "--json",
            "workflowName,status,conclusion,createdAt,url",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    rows = json.loads(result.stdout)
    if not rows:
        return {
            "workflow": workflow,
            "status": "never_run",
            "conclusion": None,
            "created_at": None,
            "url": None,
        }
    row = rows[0]
    return {
        "workflow": str(row.get("workflowName") or workflow),
        "status": str(row.get("status") or "unknown"),
        "conclusion": row.get("conclusion"),
        "created_at": row.get("createdAt"),
        "url": row.get("url"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        rows = [workflow_status(workflow) for workflow in WORKFLOWS]
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Backtest status unavailable: {type(exc).__name__}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            result = row["conclusion"] or row["status"]
            print(f"{row['workflow']}: {result} ({row['created_at'] or 'never'})")
            if row["url"]:
                print(f"  {row['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
