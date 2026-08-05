"""Anonymize expired UGC abuse/contact metadata.

Run daily from the platform scheduler. Content and account ownership remain;
only short-lived IP hashes and optional contact addresses are removed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from sqlalchemy import update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import ImageReport, LocalTip, SpotImage, SpotRating, SpotSubmission


def run() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=get_settings().ugc_personal_data_retention_days
    )
    total = 0
    with SessionLocal() as db:
        for model, email_field in (
            (SpotRating, "author_email"),
            (LocalTip, "author_email"),
            (SpotSubmission, "submitter_email"),
            (SpotImage, "submitter_email"),
            (ImageReport, "reporter_email"),
        ):
            result = db.execute(
                update(model)
                .where(model.created_at < cutoff)
                .values({"ip_hash": None, email_field: None})
            )
            total += result.rowcount or 0
        db.commit()
    return total


if __name__ == "__main__":
    print(f"Anonymized {run()} expired UGC records.")
