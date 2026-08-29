"""Read-only Neon transfer-quota guard for scheduled background work.

The project detail endpoint is available on Neon's Free plan and its
``data_transfer_bytes`` value is the running total for the current billing
period. API calls do not connect to Postgres or wake its compute.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

WARNING_BYTES = 3_000_000_000
CRITICAL_BYTES = 4_000_000_000
BLOCK_BYTES = 4_500_000_000
FREE_TRANSFER_BYTES = 5_000_000_000


def transfer_level(data_transfer_bytes: int) -> str:
    if data_transfer_bytes >= BLOCK_BYTES:
        return "blocked"
    if data_transfer_bytes >= CRITICAL_BYTES:
        return "critical"
    if data_transfer_bytes >= WARNING_BYTES:
        return "warning"
    return "ok"


def fetch_project_transfer(
    api_key: str,
    project_id: str,
    *,
    opener: Callable = urlopen,
) -> int:
    url = (
        "https://console.neon.tech/api/v2/projects/"
        f"{quote(project_id, safe='-')}"
    )
    request = Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    with opener(request, timeout=15) as response:
        payload = json.load(response)
    value = (payload.get("project") or {}).get("data_transfer_bytes")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("Neon response has no valid data_transfer_bytes value")
    return value


def _append_key_values(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def _append_summary(text: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as summary:
        summary.write(text + "\n")


def _annotation(kind: str, title: str, message: str) -> None:
    safe_title = title.replace("\n", " ").replace("\r", " ")
    safe_message = message.replace("\n", " ").replace("\r", " ")
    print(f"::{kind} title={safe_title}::{safe_message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)

    api_key = os.getenv("NEON_API_KEY", "").strip()
    project_id = os.getenv("NEON_PROJECT_ID", "").strip()
    if not api_key or not project_id:
        _append_key_values(
            args.github_output,
            {"configured": "false", "allow_shadow": "false", "level": "unconfigured"},
        )
        _annotation(
            "warning",
            "Neon transfer guard is not configured",
            "Shadow collection remains paused; set NEON_API_KEY and NEON_PROJECT_ID.",
        )
        _append_summary(
            "### Neon transfer guard\nNot configured. Weather Shadow remains paused."
        )
        return 0

    try:
        used = fetch_project_transfer(api_key, project_id)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        _append_key_values(
            args.github_output,
            {"configured": "true", "allow_shadow": "false", "level": "error"},
        )
        _annotation(
            "error",
            "Neon transfer guard failed",
            f"Quota could not be read ({type(exc).__name__}); Shadow collection is blocked.",
        )
        _append_summary(
            "### Neon transfer guard\nQuota check failed. Weather Shadow was blocked."
        )
        return 1

    level = transfer_level(used)
    allow_shadow = level != "blocked"
    used_gb = used / 1_000_000_000
    _append_key_values(
        args.github_output,
        {
            "configured": "true",
            "allow_shadow": str(allow_shadow).lower(),
            "level": level,
            "used_bytes": str(used),
        },
    )
    _append_summary(
        "### Neon transfer guard\n"
        f"{used_gb:.3f} GB of {FREE_TRANSFER_BYTES / 1_000_000_000:.1f} GB "
        f"used — status **{level}**; Shadow allowed: **{str(allow_shadow).lower()}**."
    )

    if level == "blocked":
        _annotation(
            "error",
            "Neon transfer at 4.5 GB stop threshold",
            f"{used_gb:.3f} GB used; Weather Shadow was blocked to preserve production traffic.",
        )
        return 2
    if level in {"warning", "critical"}:
        threshold = "4 GB critical" if level == "critical" else "3 GB warning"
        _annotation(
            "warning",
            f"Neon transfer {threshold}",
            f"{used_gb:.3f} GB used in the current billing period.",
        )
    else:
        print(f"Neon transfer guard: {used_gb:.3f} GB used; status ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
