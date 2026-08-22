"""Process exactly one explicitly queued V3 shadow run.

There is deliberately no catalogue/all-spots mode in phases 1–3.
"""

from __future__ import annotations

import argparse
import json
import uuid

from app.db.session import SessionLocal
from app.wind_climatology.v3_service import process


def main(run_id: uuid.UUID) -> dict:
    with SessionLocal() as db:
        run = process(db, run_id)
        result = {"run_id": str(run.id), "status": run.status, "variant_count": run.variant_count, "artifact_bytes": run.artifact_bytes, "public_effect": "none"}
        print(json.dumps(result))
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    main(args.run_id)
