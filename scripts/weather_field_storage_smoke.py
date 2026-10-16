"""Non-destructive smoke test for the configured forecast object store."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import secrets
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.spatial_fields.storage import configured_field_storage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="keep the smoke object")
    args = parser.parse_args()
    storage = configured_field_storage()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"smoke/{stamp}-{secrets.token_hex(8)}.txt"
    payload = f"surfwinddata-storage-smoke:{stamp}".encode()
    stored = storage.put_immutable(key, payload)
    try:
        if not storage.exists(key):
            raise RuntimeError("uploaded smoke object is not visible")
        if storage.get(key) != payload:
            raise RuntimeError("downloaded smoke object differs from upload")
        if not stored.public_url.startswith(("/", "https://")):
            raise RuntimeError("public URL must be root-relative or HTTPS")
        print(
            f"storage_smoke=passed backend={type(storage).__name__} "
            f"bytes={stored.size_bytes} public_url={stored.public_url}"
        )
    finally:
        if not args.keep:
            storage.delete(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
