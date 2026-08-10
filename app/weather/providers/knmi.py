"""KNMI Open Data access seam; parsing is enabled once a registered key is configured."""

from __future__ import annotations

import httpx

KNMI_BASE = "https://api.dataplatform.knmi.nl/open-data/v1"
DATASET = "10-minute-in-situ-meteorological-observations"
VERSION = "1.0"


class KnmiOpenDataClient:
    def __init__(self, api_key: str, *, timeout: float = 20.0) -> None:
        if not api_key.strip():
            raise ValueError("KNMI API key is required")
        self.api_key, self.timeout = api_key, timeout

    def latest_files(self, limit: int = 2) -> list[dict]:
        response = httpx.get(
            f"{KNMI_BASE}/datasets/{DATASET}/versions/{VERSION}/files",
            headers={"Authorization": self.api_key},
            params={"maxKeys": max(1, min(limit, 20)), "sorting": "desc"}, timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("files") or []

    def download_url(self, filename: str) -> str:
        response = httpx.get(
            f"{KNMI_BASE}/datasets/{DATASET}/versions/{VERSION}/files/{filename}/url",
            headers={"Authorization": self.api_key}, timeout=self.timeout,
        )
        response.raise_for_status()
        return str(response.json()["temporaryDownloadUrl"])
