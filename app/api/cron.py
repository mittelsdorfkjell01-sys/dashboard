"""Authenticated maintenance endpoints invoked by Vercel Cron."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.admin.deps import get_extract_client
from app.config import get_settings
from app.db.session import get_db

router = APIRouter(prefix="/cron", tags=["maintenance"])


def _require_cron(request: Request) -> None:
    expected = get_settings().cron_secret
    provided = request.headers.get("Authorization")
    if not expected:
        raise HTTPException(status_code=503, detail="Cron maintenance is not configured.")
    if not provided or not secrets.compare_digest(provided, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/climatology", dependencies=[Depends(_require_cron)])
def maintain_climatology(
    db: Session = Depends(get_db),
    client=Depends(get_extract_client),
) -> dict:
    """Queue stale snapshots and process a bounded daily batch."""
    from app.admin.era5_worker import process_due_batch

    return process_due_batch(
        db,
        client=client,
        limit=min(max(get_settings().climatology_cron_batch_size, 1), 5),
    )
