"""Export the media-critical catalogue state before a production migration."""

from __future__ import annotations

import gzip
import json
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import MediaUsage, Spot, SpotAudit, SpotImage


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _rows(db, model, columns):
    result = db.execute(select(*(getattr(model, name) for name in columns))).all()
    return [
        {name: _json(value) for name, value in zip(columns, row, strict=True)}
        for row in result
    ]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: export_catalog_backup.py OUTPUT.json.gz")
    output = Path(sys.argv[1]).resolve()
    with SessionLocal() as db:
        payload = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "spots": _rows(db, Spot, ["id", "slug", "name", "image", "updated_at"]),
            "spot_images": _rows(db, SpotImage, [
                "id", "spot_id", "region_id", "url", "kind", "width", "height",
                "source", "credit", "license_name", "license_url", "source_url",
                "provider", "external_id", "credit_url", "retrieved_at", "delivery",
                "geo_verified", "position", "status", "created_at", "updated_at",
            ]),
            "media_usage": _rows(db, MediaUsage, [
                "id", "provider", "external_id", "entity_type", "entity_id", "role",
                "created_at", "updated_at",
            ]),
            "spot_audit": _rows(db, SpotAudit, [
                "id", "spot_id", "actor", "action", "changes", "created_at",
            ]),
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, default=_json)
    print(f"catalog backup: {len(payload['spots'])} spots, {len(payload['spot_images'])} images")


if __name__ == "__main__":
    main()
