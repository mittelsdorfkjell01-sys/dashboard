"""Local fixture/dry-run entry point; intentionally not scheduled."""
import argparse, json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args()
    settings = get_settings()
    if settings.app_env == "production" or settings.database_target != "local":
        raise SystemExit("observation import is restricted to local dry-runs")
    print(json.dumps({"dry_run": True, "providers": ["dwd", "dmi"], "scheduled": False}))


if __name__ == "__main__": main()
