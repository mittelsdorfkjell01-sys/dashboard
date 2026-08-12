"""Versioned, validated registry for official geodata inputs."""

from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DatasetDefinition:
    key: str
    provider: str
    dataset: str
    product_instance: str
    version: str
    coverage: str
    resolution_m: float
    horizontal_crs: str
    vertical_datum: str | None
    file_format: str
    access_method: str
    base_url: str
    authentication: str
    licence_name: str
    licence_url: str
    attribution: str
    restrictions: str
    legal_checked_on: str
    commercial_review_required: bool
    checksum_strategy: str
    nodata: str
    quality_layers: tuple[str, ...]
    tile_structure: str
    fallback_key: str | None = None
    enabled: bool = True

    def validate(self) -> None:
        if (
            self.key == "cop-dem-glo30"
            and self.product_instance != "COP-DEM_GLO-30-DGED"
        ):
            raise ValueError(
                "only the free/open COP-DEM GLO-30 DGED instance is allowed"
            )
        if not self.licence_name or not self.licence_url or not self.attribution:
            raise ValueError("licence and attribution are mandatory")
        if not self.base_url.startswith("https://"):
            raise ValueError("official HTTPS source required")


COP_DEM_ATTRIBUTION = "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"
WORLDCOVER_ATTRIBUTION = "© ESA WorldCover project / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium"

GEODATASETS = {
    "cop-dem-glo30": DatasetDefinition(
        "cop-dem-glo30",
        "Copernicus Data Space Ecosystem",
        "Copernicus DEM GLO-30-F",
        "COP-DEM_GLO-30-DGED",
        "2024_1",
        "global land",
        30,
        "EPSG:4326 (WGS84-G1150)",
        "EPSG:3855 EGM2008",
        "GeoTIFF/DGED",
        "CDSE OData/S3 authenticated asset",
        "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
        "CDSE account, CCM registration and accepted licence",
        "Copernicus DEM GLO-30-F licence",
        "https://dataspace.copernicus.eu/sites/default/files/media/files/2025-06/copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf",
        COP_DEM_ATTRIBUTION,
        "DSM, not DTM; vegetation and buildings can raise elevations",
        "2026-08-12",
        True,
        "provider checksum plus local SHA-256",
        "product metadata; GLO DGED ocean cells may be absent",
        ("WBM", "HEM", "EDM", "FLM"),
        "1° x 1° geocells; longitude spacing varies with latitude",
        "cop-dem-glo90",
    ),
    "cop-dem-glo90": DatasetDefinition(
        "cop-dem-glo90",
        "Copernicus Data Space Ecosystem",
        "Copernicus DEM GLO-90-F",
        "COP-DEM_GLO-90-DGED",
        "2024_1",
        "global land",
        90,
        "EPSG:4326 (WGS84-G1150)",
        "EPSG:3855 EGM2008",
        "GeoTIFF/DGED",
        "CDSE OData/S3 authenticated asset",
        "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
        "CDSE account, CCM registration and accepted licence",
        "Copernicus DEM GLO-90-F licence",
        "https://dataspace.copernicus.eu/sites/default/files/media/files/2025-06/copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf",
        COP_DEM_ATTRIBUTION.replace("30", "90"),
        "DSM, not DTM",
        "2026-08-12",
        True,
        "provider checksum plus local SHA-256",
        "product metadata",
        ("WBM", "HEM", "EDM", "FLM"),
        "1° x 1° geocells",
    ),
    "worldcover-2021": DatasetDefinition(
        "worldcover-2021",
        "European Space Agency",
        "ESA WorldCover 2021",
        "ESA_WorldCover_10m_2021_v200",
        "v200",
        "global land",
        10,
        "EPSG:4326",
        None,
        "Cloud Optimized GeoTIFF",
        "public HTTPS/S3 range requests",
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021",
        "none",
        "CC BY 4.0",
        "https://creativecommons.org/licenses/by/4.0/",
        WORLDCOVER_ATTRIBUTION,
        "11-class model output; not pixel-perfect ground truth",
        "2026-08-12",
        False,
        "ETag plus local SHA-256",
        "0",
        ("InputQuality",),
        "3° x 3° COG tiles",
        "copernicus-glc100",
    ),
    "copernicus-glc100": DatasetDefinition(
        "copernicus-glc100",
        "Copernicus Global Land Service",
        "Global Land Cover",
        "CGLS-LC100 collection 3 epoch 2019",
        "v3.0.1",
        "global land",
        100,
        "EPSG:4326",
        None,
        "GeoTIFF",
        "registered fallback",
        "https://land.copernicus.eu/global/products/lc",
        "source-specific",
        "Copernicus free and open data",
        "https://land.copernicus.eu/en/data-policy",
        "© European Union, Copernicus Land Monitoring Service",
        "Prepared fallback only; downloader disabled in phase 1",
        "2026-08-12",
        True,
        "local SHA-256",
        "dataset metadata",
        (),
        "global tiled raster",
        enabled=False,
    ),
}


def validate_catalog() -> None:
    for item in GEODATASETS.values():
        item.validate()
        if item.fallback_key and item.fallback_key not in GEODATASETS:
            raise ValueError(f"unknown fallback {item.fallback_key}")


def sync_catalog(db) -> None:
    from sqlalchemy import select
    from app.models import GeodataDataset

    validate_catalog()
    for definition in GEODATASETS.values():
        row = db.scalar(
            select(GeodataDataset).where(
                GeodataDataset.key == definition.key,
                GeodataDataset.version == definition.version,
            )
        )
        if row:
            continue
        raw = asdict(definition)
        db.add(
            GeodataDataset(
                key=definition.key,
                version=definition.version,
                provider=definition.provider,
                product_instance=definition.product_instance,
                status="enabled" if definition.enabled else "registered",
                specification={
                    k: raw[k]
                    for k in (
                        "dataset",
                        "coverage",
                        "resolution_m",
                        "horizontal_crs",
                        "vertical_datum",
                        "file_format",
                        "access_method",
                        "base_url",
                        "authentication",
                        "checksum_strategy",
                        "nodata",
                        "quality_layers",
                        "tile_structure",
                    )
                },
                licence={
                    "name": definition.licence_name,
                    "url": definition.licence_url,
                    "attribution": definition.attribution,
                    "restrictions": definition.restrictions,
                    "commercial_review_required": definition.commercial_review_required,
                },
                fallback_key=definition.fallback_key,
                legal_checked_at=datetime.fromisoformat(
                    definition.legal_checked_on
                ).replace(tzinfo=timezone.utc),
                active=definition.enabled,
            )
        )
    db.flush()
