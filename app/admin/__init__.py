"""Admin / data-maintenance workflow (Sprint 8).

A complete write path — create spots & regions, curate editorial (incl. free
text), override auto-computed values with provenance + audit, manage image rights,
and publish a spot only once it is *ready*. Pure API/logic, no UI.

Auth is out of scope for this sprint: the ``/admin`` endpoints are unprotected by
default, optionally gated by a shared ``ADMIN_KEY`` (``X-Admin-Key`` header).
"""

from app.admin.constants import NA, STATUS_DRAFT, STATUS_LIVE
from app.admin.readiness import validate_spot_readiness
from app.admin.regions import (
    assign_spot_to_region,
    create_region,
    update_region_defaults,
)
from app.admin.jobs import get_job_status, trigger_era5_job
from app.admin.spots import (
    create_spot,
    manage_spot_image,
    override_auto_field,
    revert_override,
    set_spot_live,
    spot_effective_view,
    update_spot,
    update_spot_metadata,
)

__all__ = [
    "NA",
    "STATUS_DRAFT",
    "STATUS_LIVE",
    "create_spot",
    "update_spot",
    "update_spot_metadata",
    "override_auto_field",
    "revert_override",
    "manage_spot_image",
    "set_spot_live",
    "spot_effective_view",
    "validate_spot_readiness",
    "create_region",
    "assign_spot_to_region",
    "update_region_defaults",
    "trigger_era5_job",
    "get_job_status",
]
