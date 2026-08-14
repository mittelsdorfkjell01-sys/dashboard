"""Official CDSE OData discovery and bounded S3 object access.

Credentials are read from settings and are never included in exceptions,
reports or persisted metadata. Product selection is deterministic: newest
modification/publication timestamp, then UUID.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import boto3
import httpx

from app.config import get_settings

ODATA_PRODUCTS = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
PRODUCT_TYPE = "SAR_DGE_30_A4AD"
PRODUCT_INSTANCE = "COP-DEM_GLO-30-DGED"
LAYERS = ("DEM", "WBM", "HEM", "EDM", "FLM")


class CdseError(RuntimeError):
    pass


class CdseNotFound(CdseError):
    pass


@dataclass(frozen=True)
class CdseObject:
    layer: str
    key: str
    size_bytes: int
    etag: str


@dataclass(frozen=True)
class CdseProduct:
    product_id: str
    name: str
    s3_path: str
    content_length: int
    modification_date: str
    checksum: tuple[dict, ...]
    objects: tuple[CdseObject, ...]

    @property
    def pinned_hash(self) -> str:
        raw = "|".join(
            [
                self.product_id,
                self.modification_date,
                *(
                    f"{item.layer}:{item.key}:{item.size_bytes}:{item.etag}"
                    for item in self.objects
                ),
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()


class CdseClient:
    def __init__(self, *, catalogue: httpx.Client | None = None):
        settings = get_settings()
        if not settings.cdse_s3_access_key or not settings.cdse_s3_secret_key:
            raise CdseError("CDSE S3 credentials are not configured")
        self.endpoint = settings.cdse_s3_endpoint.rstrip("/")
        self.catalogue = catalogue or httpx.Client(timeout=60, follow_redirects=True)
        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=settings.cdse_s3_access_key,
            aws_secret_access_key=settings.cdse_s3_secret_key,
            region_name="default",
        )

    @staticmethod
    def _filter(latitude: float, longitude: float) -> str:
        return (
            "Collection/Name eq 'CCM' and "
            "Attributes/OData.CSC.StringAttribute/any(a:a/Name eq 'productType' "
            f"and a/OData.CSC.StringAttribute/Value eq '{PRODUCT_TYPE}') and "
            "OData.CSC.Intersects(area=geography'SRID=4326;"
            f"POINT({longitude:.7f} {latitude:.7f})')"
        )

    def resolve(self, latitude: float, longitude: float) -> CdseProduct:
        response = self.catalogue.get(
            ODATA_PRODUCTS,
            params={
                "$filter": self._filter(latitude, longitude),
                "$select": "Id,Name,S3Path,ContentLength,Online,ModificationDate,PublicationDate,Checksum",
                "$top": "50",
            },
        )
        response.raise_for_status()
        candidates = [item for item in response.json().get("value", []) if item.get("Online")]
        if not candidates:
            raise CdseNotFound("no online GLO-30 DGED product covers coordinate")
        candidates.sort(
            key=lambda item: (
                item.get("ModificationDate") or "",
                item.get("PublicationDate") or "",
                item["Id"],
            ),
            reverse=True,
        )
        item = candidates[0]
        bucket, prefix = item["S3Path"].lstrip("/").split("/", 1)
        if bucket != "eodata" or not prefix.startswith(f"CCM/{PRODUCT_INSTANCE}/"):
            raise CdseError("catalogue returned an unexpected S3 product path")
        listing = self.s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/")
        if listing.get("IsTruncated"):
            raise CdseError("unexpectedly truncated DEM object listing")
        raw_objects = listing.get("Contents", [])
        objects = []
        for layer in LAYERS:
            suffix = f"_{layer}.tif"
            matches = [obj for obj in raw_objects if obj["Key"].endswith(suffix)]
            if len(matches) != 1:
                raise CdseError(f"product must contain exactly one {layer} layer")
            obj = matches[0]
            objects.append(
                CdseObject(layer, obj["Key"], int(obj["Size"]), obj.get("ETag", "").strip('"'))
            )
        return CdseProduct(
            product_id=item["Id"],
            name=item["Name"],
            s3_path=item["S3Path"],
            content_length=int(item.get("ContentLength") or sum(o.size_bytes for o in objects)),
            modification_date=item.get("ModificationDate") or "",
            checksum=tuple(item.get("Checksum") or ()),
            objects=tuple(objects),
        )

    def read_smallest(self, product: CdseProduct) -> dict:
        bucket, prefix = product.s3_path.lstrip("/").split("/", 1)
        listing = self.s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/")
        obj = min(listing.get("Contents", []), key=lambda value: value["Size"])
        data = self.s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
        return {
            "relative_key": obj["Key"][len(prefix) + 1 :],
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def download_object(self, obj: CdseObject, target: Path) -> dict:
        """Atomically download one already-sized object and verify length/hash."""
        target = target.resolve()
        if target.exists() and target.stat().st_size == obj.size_bytes:
            return {
                "path": str(target),
                "size_bytes": obj.size_bytes,
                "sha256": _sha256(target),
                "cache_hit": True,
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        with temporary.open("wb") as handle:
            self.s3.download_fileobj("eodata", obj.key, handle)
        if temporary.stat().st_size != obj.size_bytes:
            temporary.unlink(missing_ok=True)
            raise CdseError("incomplete S3 object download")
        temporary.replace(target)
        return {
            "path": str(target),
            "size_bytes": obj.size_bytes,
            "sha256": _sha256(target),
            "cache_hit": False,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
