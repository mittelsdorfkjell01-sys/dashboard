"""Bounded atomic cache for reproducible raster assets and byte windows."""

from __future__ import annotations
import hashlib
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx


class RasterLimitExceeded(RuntimeError):
    pass


@dataclass
class RunBudget:
    max_download_bytes: int
    max_asset_bytes: int
    max_temp_bytes: int
    downloaded: int = 0
    temporary: int = 0
    requests: int = 0
    retries: int = 0
    ranges: list[dict] = field(default_factory=list)

    def consume(
        self,
        size: int,
        *,
        content_length: int | None = None,
        byte_range: str | None = None,
    ) -> None:
        if size > self.max_asset_bytes:
            raise RasterLimitExceeded(
                f"single asset limit {self.max_asset_bytes} bytes exceeded"
            )
        if self.downloaded + size > self.max_download_bytes:
            raise RasterLimitExceeded(
                f"run download limit {self.max_download_bytes} bytes exceeded"
            )
        if self.temporary + size > self.max_temp_bytes:
            raise RasterLimitExceeded(
                f"temporary storage limit {self.max_temp_bytes} bytes exceeded"
            )
        self.downloaded += size
        self.temporary += size
        self.requests += 1
        self.ranges.append(
            {"range": byte_range, "bytes": size, "content_length": content_length}
        )


_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()
_download_slots = threading.BoundedSemaphore(2)


def _lock(key: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(key, threading.Lock())


class RasterCache:
    def __init__(
        self,
        root: str | Path,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20,
        retries: int = 3,
        daily_limit_bytes: int | None = None,
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.Client(follow_redirects=True)
        self.timeout = timeout
        self.retries = min(3, max(0, retries))
        self.daily_limit_bytes = daily_limit_bytes

    def _consume_daily(self, size: int) -> None:
        if self.daily_limit_bytes is None:
            return
        ledger = self.root / ".daily-bytes.json"
        today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
        with _guard:
            state = (
                json.loads(ledger.read_text(encoding="utf-8"))
                if ledger.exists()
                else {}
            )
            used = int(state.get(today, 0))
            if used + size > self.daily_limit_bytes:
                raise RasterLimitExceeded(
                    f"Berlin daily download limit {self.daily_limit_bytes} bytes exceeded"
                )
            temporary = ledger.with_suffix(".part")
            temporary.write_text(json.dumps({today: used + size}), encoding="utf-8")
            temporary.replace(ledger)

    def path_for(
        self, dataset: str, version: str, asset_key: str, byte_range: str | None
    ) -> Path:
        digest = hashlib.sha256(
            f"{dataset}:{version}:{asset_key}:{byte_range or 'full'}".encode()
        ).hexdigest()
        return self.root / dataset / version / digest[:2] / digest

    def fetch(
        self,
        url: str,
        *,
        dataset: str,
        version: str,
        asset_key: str,
        budget: RunBudget,
        byte_range: tuple[int, int] | None = None,
    ) -> tuple[Path, dict]:
        if not url.startswith("https://") or "*" in url:
            raise ValueError("only one explicit HTTPS asset may be fetched")
        range_value = f"bytes={byte_range[0]}-{byte_range[1]}" if byte_range else None
        target = self.path_for(dataset, version, asset_key, range_value)
        if target.exists():
            return target, {
                "cache_hit": True,
                "bytes": 0,
                "checksum": hashlib.sha256(target.read_bytes()).hexdigest(),
                "range": range_value,
            }
        with _lock(str(target)):
            if target.exists():
                return target, {
                    "cache_hit": True,
                    "bytes": 0,
                    "checksum": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "range": range_value,
                }
            headers = {"User-Agent": "surfwinddata-geoprofile/1.0"}
            if range_value:
                headers["Range"] = range_value
            response = None
            for attempt in range(self.retries + 1):
                try:
                    with _download_slots:
                        response = self.client.get(
                            url, headers=headers, timeout=self.timeout
                        )
                    response.raise_for_status()
                    break
                except httpx.HTTPError:
                    if attempt >= self.retries:
                        raise
                    budget.retries += 1
                    time.sleep(min(2, 0.15 * (2**attempt)) + random.random() * 0.05)
            assert response is not None
            if byte_range and response.status_code != 206:
                raise RasterLimitExceeded(
                    "server ignored Range request; full asset download refused"
                )
            data = response.content
            content_length = (
                int(response.headers["content-length"])
                if response.headers.get("content-length", "").isdigit()
                else None
            )
            budget.consume(
                len(data), content_length=content_length, byte_range=range_value
            )
            self._consume_daily(len(data))
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(
                f".part-{os.getpid()}-{threading.get_ident()}"
            )
            temporary.write_bytes(data)
            checksum = hashlib.sha256(data).hexdigest()
            if temporary.stat().st_size != len(data):
                temporary.unlink(missing_ok=True)
                raise IOError("incomplete cache write")
            temporary.replace(target)
            budget.temporary -= len(data)
            return target, {
                "cache_hit": False,
                "bytes": len(data),
                "checksum": checksum,
                "range": range_value,
                "content_length": content_length,
                "status": response.status_code,
            }

    def cleanup(self, *, max_bytes: int, protected: set[Path] | None = None) -> int:
        protected = {p.resolve() for p in (protected or set())}
        files = [
            p for p in self.root.rglob("*") if p.is_file() and ".part-" not in p.name
        ]
        total = sum(p.stat().st_size for p in files)
        removed = 0
        for path in sorted(files, key=lambda p: p.stat().st_atime):
            if total <= max_bytes:
                break
            if path.resolve() in protected:
                continue
            size = path.stat().st_size
            path.unlink()
            total -= size
            removed += 1
        return removed
