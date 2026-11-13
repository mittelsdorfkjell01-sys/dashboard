"""Small operational admin surface, separate from catalogue write routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_role
from app.config import get_settings
from app.db.session import get_db

router = APIRouter(
    prefix="/admin",
    tags=["admin-operations"],
    dependencies=[Depends(require_role("admin", "curator"))],
)


@router.get("/environment")
def environment() -> dict:
    """Return the write-safety target without exposing connection details."""
    return get_settings().environment_summary()


@router.get("/operations")
def operations(db: Session = Depends(get_db)) -> dict:
    """Return job, freshness and bounded process-local cache evidence."""
    from app.admin import operations as admin_operations

    return admin_operations.operations_summary(db)
