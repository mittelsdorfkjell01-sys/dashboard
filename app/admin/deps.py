"""Admin FastAPI dependencies: climatology-extract client and stock client.

Auth moved to :mod:`app.auth.deps` in Sprint A (cookie session + roles). The old
``require_admin`` shared-key gate was removed from here; the optional break-glass
``X-Admin-Key`` is handled inside ``app.auth.deps.current_user``.
"""

from __future__ import annotations

from app.admin.commons import CommonsClient, default_commons_client
from app.admin.stock import StockImageClient, default_stock_client


def get_extract_client():
    """Climatology extraction client — **Open-Meteo Historical** by default.

    Wind/temperature from the ERA5 archive-api, waves from the marine-api; plain
    HTTP, no ``cdsapi`` / ``~/.cdsapirc`` needed. Constructing it does no network
    (fetching happens lazily in ``fetch_series``). Tests override this dependency
    with a fake client that returns a canned series.
    """
    from app.era5.batch import retrying_http
    from app.era5.openmeteo import OpenMeteoHistoryClient

    # One bounded retry keeps the complete two-request calculation inside the
    # 60-second Vercel function limit even when an upstream request times out.
    return OpenMeteoHistoryClient(http=retrying_http(retries=1, timeout=12.0))


# Backward-compatible alias: the seam used to be CDS-specific. Kept so existing
# dependency overrides (tests) keep working. The optional CDS adapter lives in
# app.era5.cds.real_cds_client() and is no longer on the default path.
get_cds_client = get_extract_client


def get_stock_client() -> StockImageClient:
    return default_stock_client()


def get_commons_client() -> CommonsClient:
    return default_commons_client()
