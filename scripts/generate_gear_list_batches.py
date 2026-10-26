"""Generate reviewed staging batches from the 2026-10-24 gear-list research.

The compact definitions below are intentionally separated from catalogue data:
the generated JSON remains the auditable import boundary. Unknown seasons stay
unknown and no numeric kite wind ranges are emitted.
"""

from __future__ import annotations

import json
from pathlib import Path


CHECKED_AT = "2026-10-24T12:00:00+02:00"
RIGHTS = "Facts only. No manufacturer images, logos or traced artwork are included."
OUT = Path("research/gear/staging")


SOURCES = {
    "core_legacy": ("https://publish.corekites.com/files/CORE_ProductGuide_2016_2017_EN.pdf", "CORE Product Guide 2016/2017", "CORE", "manufacturer_catalog"),
    "core_roadmap": ("https://support.corekites.com/en/support/solutions/articles/136210-how-long-will-you-carry-parts-for-my-core-product-kite-bar-board-", "CORE official product support roadmap", "CORE", "manufacturer_page"),
    "duotone_2021": ("https://www.duotonesports.com/booklet/DT21-Whats-New/DT21-Whats-New/assets/common/downloads/Duotone%20What.pdf", "Duotone What's New 2021", "Duotone", "manufacturer_catalog"),
    "duotone_2025": ("https://www.duotonesports.com/en/products/duotone-rebel-d-lab-2025-44250-3009", "Duotone Rebel D/LAB 2025", "Duotone", "manufacturer_page"),
    "north_archive": ("https://www.duotonesports.com/en/kiteboarding/more/about-us/history", "Official North/Duotone brand history and archive", "Duotone", "manufacturer_page"),
    "cabrinha_2016": ("https://www.cabrinha.com/pages/product-catalog", "Cabrinha official product catalog archive", "Cabrinha", "manufacturer_catalog"),
    "fone_2019": ("https://www.f-one.world/app/uploads/2018/08/F-ONE-2019-Kite-collection-EN.pdf", "F-One 2019 Kite Collection", "F-One", "manufacturer_catalog"),
    "fone_archive": ("https://www.f-one.world/downloads/", "F-One official downloads archive", "F-One", "manufacturer_catalog"),
    "ozone_enduro": ("https://ozonekites.com/app/uploads/products/Enduro-V1-Info.pdf", "Ozone Enduro V1 official product information", "Ozone", "manufacturer_manual"),
    "ozone_current": ("https://ozonekites.com/kite/kites/", "Ozone current kite collection", "Ozone", "manufacturer_page"),
    "naish_2026": ("https://www.naish.com/collections/kites", "Naish official kite collection", "Naish", "manufacturer_page"),
    "naish_pivot": ("https://www.naish.com/products/pivot-new-2026", "Naish Pivot 2026", "Naish", "manufacturer_page"),
    "slingshot": ("https://slingshotsports.com/collections/kites", "Slingshot official kite collection and archive", "Slingshot", "manufacturer_page"),
    "airush": ("https://airush.com/collections/kites", "Airush official kite collection", "Airush", "manufacturer_page"),
    "airush_ultra": ("https://airush.com/blogs/news/ultra-team-ds-double-surface-technology", "Airush Ultra Team DS technical article", "Airush", "manufacturer_page"),
    "eleveight": ("https://eleveight.world/kite/kites/", "Eleveight official kite collection", "Eleveight", "manufacturer_page"),
    "reedin": ("https://reedin.com/kitesurfing/kites/", "Reedin official kite collection", "Reedin", "manufacturer_page"),
    "flysurfer_downloads": ("https://flysurfer.com/services/downloads/", "FLYSURFER official manuals and line plans", "FLYSURFER", "manufacturer_manual"),
    "flysurfer_current": ("https://flysurfer.com/products/kites/", "FLYSURFER current kite collection", "FLYSURFER", "manufacturer_page"),
    "harlem": ("https://harlemkitesurfing.com/collections/kites", "Harlem official kite collection", "Harlem", "manufacturer_page"),
    "harlem_hadlow": ("https://harlemkitesurfing.com/products/hadlow-pro", "Harlem Hadlow Pro", "Harlem", "manufacturer_page"),
}


def source(key: str) -> dict:
    url, title, publisher, source_type = SOURCES[key]
    return {
        "url": url,
        "title": title,
        "publisher": publisher,
        "type": source_type,
        "checkedAt": CHECKED_AT,
        "rights": "Facts only; no manufacturer imagery or protected artwork copied.",
    }


def add_model(
    records: list[dict], *, brand: str, name: str, season: str, source_key: str,
    sizes: list[float] | None = None, model_year: int | None = None,
    status: str = "verified", uncertainty: str | None = None,
    uses: list[str] | None = None, compatibility: list[dict] | None = None,
) -> None:
    src = source(source_key)
    presence = {
        "field": "catalogue_presence",
        "value": f"{name} is listed in the cited official manufacturer source.",
        "status": status,
    }
    if uncertainty:
        presence["uncertainty"] = uncertainty
    base = {
        "brand": brand,
        "name": name,
        "category": "kite",
        "season": season,
        "modelYear": model_year,
        "source": src,
        "claims": [presence],
    }
    for use in uses or []:
        base["claims"].append({"field": "intended_use", "value": use, "status": status})
    profile_map = {
        "all-round": ("all_round", "all_conditions"),
        "big-air": ("big_air", "all_conditions"),
        "freeride": ("freeride", "all_conditions"),
        "freestyle": ("freestyle", "flat_water"),
        "foil": ("foil", "all_conditions"),
        "light-wind": ("freeride", "light_wind"),
        "race": ("race", "all_conditions"),
        "school": ("school", "all_conditions"),
        "wave": ("wave", "waves"),
    }
    if uses:
        base["useProfiles"] = [
            {
                "sport": "kitesurf",
                "discipline": profile_map[use][0],
                "condition": profile_map[use][1],
                "suitability": "designed_for",
                "status": status,
            }
            for use in uses
        ]
    if compatibility:
        base["compatibility"] = compatibility
    records.append(base)
    for value in sizes or []:
        claim = {"field": "available_size", "value": value, "unit": "m²", "status": status}
        if uncertainty:
            claim["uncertainty"] = uncertainty
        records.append({
            "brand": brand,
            "name": name,
            "category": "kite",
            "season": season,
            "modelYear": model_year,
            "size": {"label": f"{value:g} m²", "value": value, "unit": "m²"},
            "source": src,
            "claims": [claim],
        })


def range_sizes(start: int, end: int) -> list[float]:
    return [float(value) for value in range(start, end + 1)]


def write_batch(name: str, scope: str, records: list[dict]) -> None:
    document = {
        "reviewStatus": "accepted_for_import",
        "checkedAt": CHECKED_AT,
        "rights": RIGHTS,
        "researchScope": scope,
        "records": records,
    }
    path = OUT / name
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def core_duotone_north() -> None:
    records: list[dict] = []
    legacy = [5, 6, 7, 8, 9, 10, 11, 12, 13.5]
    add_model(records, brand="CORE", name="XR4", season="2016/2017", source_key="core_legacy", sizes=legacy)
    add_model(records, brand="CORE", name="XR4 LW", season="2016/2017", source_key="core_legacy", sizes=[15, 17, 19])
    add_model(records, brand="CORE", name="GTS4", season="2016/2017", source_key="core_legacy", sizes=legacy)
    add_model(records, brand="CORE", name="GTS4 LW", season="2016/2017", source_key="core_legacy", sizes=[15, 17])
    for name in ["XR5", "Section 2", "Impact 2", "GTS5", "XR6", "Section 3", "XLite", "Nexus 2", "XR7", "Section 4", "XLite 2", "Nexus 3", "XR Pro", "XR8", "Nexus 4", "Pace Pro", "Section 5", "XR Pro 2", "PACE", "Air", "Air Pro", "XRX", "NXS"]:
        add_model(records, brand="CORE", name=name, season="Unknown", source_key="core_roadmap", status="review", uncertainty="Official model presence is retained; exact manufacturer season and sizes remain unresolved.")

    duotone = {
        "Neo SLS": (range_sizes(5, 12), ["wave"]),
        "Neo": (range_sizes(3, 12), ["wave"]),
        "Evo SLS": (range_sizes(7, 12), ["all-round"]),
        "Evo": (range_sizes(4, 14), ["all-round", "big-air"]),
        "Dice": (range_sizes(5, 13), ["big-air", "freestyle"]),
        "Rebel": (range_sizes(5, 15), ["freeride", "big-air"]),
        "Vegas": ([6, 7, 8, 9, 10, 11, 12, 13, 14.5], ["freestyle"]),
        "Mono": ([3.5, 5, 7, 9, 11, 13, 15], ["all-round"]),
        "Juice": ([13, 15, 17], ["light-wind", "foil"]),
        "Juice D/LAB": ([13, 15], ["light-wind"]),
        "Capa": ([9, 11, 13, 15], ["freeride"]),
    }
    for name, (sizes, uses) in duotone.items():
        add_model(records, brand="Duotone", name=name, season="2021", model_year=2021, source_key="duotone_2021", sizes=sizes, uses=uses)
    add_model(records, brand="Duotone", name="Rebel D/LAB", season="2025", model_year=2025, source_key="duotone_2025", sizes=range_sizes(6, 12), uses=["big-air", "freeride"])

    for name in ["Dice", "Neo", "Vegas", "Evo", "Mono", "Rebel", "Juice", "Dyno", "Buzz Trainer", "Lizard Trainer"]:
        add_model(records, brand="North", name=name, season="2016–2018 archive", source_key="north_archive", status="review", uncertainty="Legacy North identity is separate from the post-2018 North brand; exact season and sizes remain unresolved.")
    write_batch("remaining-core-duotone-north-2026-10-24.json", "All remaining CORE, Duotone and legacy North models named in the supplied research list.", records)


def cabrinha_fone() -> None:
    records: list[dict] = []
    for name, sizes in {
        "FX": [6, 7, 8, 9, 10, 12, 14],
        "Switchblade": [4, 5, 6, 7, 8, 9, 10, 11, 12, 14],
        "Radar": [3.5, 5, 7, 9, 10, 12, 14],
        "Drifter": [4.5, 5.5, 7, 8, 9, 11, 13],
        "Contra": [13, 15, 17],
        "Velocity": [7, 9, 10, 11, 13, 14, 16, 18],
        "Chaos": [7, 9, 11, 13],
        "Genesis/Spark Trainer": [2],
    }.items():
        add_model(records, brand="Cabrinha", name=name, season="2016", model_year=2016, source_key="cabrinha_2016", sizes=sizes, status="review", uncertainty="Sizes are transcribed from the supplied research list and remain flagged for page-level archive reconfirmation.")

    for name in ["Diablo V1", "Diablo V2"]:
        add_model(records, brand="F-One", name=name, season="2017", model_year=2017, source_key="fone_archive", sizes=[7, 9, 11, 13, 15, 18], status="review", uncertainty="The supplied list groups V1 and V2; variant-specific official archive confirmation remains open.")
    add_model(records, brand="F-One", name="Bandit", season="2018", model_year=2018, source_key="fone_archive", sizes=[4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 17], status="review")
    add_model(records, brand="F-One", name="Breeze", season="2018", model_year=2018, source_key="fone_archive", sizes=[11, 13, 15], status="review")
    for name, sizes in {
        "Bandit": [4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 17],
        "Breeze": [5, 6, 7, 8, 9, 11, 13, 15],
        "Furtive": [5, 6.4, 8, 10, 12, 14, 17, 19],
        "Trust": [4, 5, 6, 7, 8, 9, 11, 13],
    }.items():
        add_model(records, brand="F-One", name=name, season="2019", model_year=2019, source_key="fone_2019", sizes=sizes)
    for name, sizes in {
        "Bandit": [7, 8, 9, 10, 11, 12, 14, 17],
        "Bandit-S": [4, 5, 6, 7, 8, 9, 10],
        "WTF!? V2": [5, 6, 7, 8, 9, 11, 13, 15],
        "Breeze V2": [3, 4, 5, 7, 9, 11, 13, 15, 17],
    }.items():
        add_model(records, brand="F-One", name=name, season="2020", model_year=2020, source_key="fone_archive", sizes=sizes, status="review")
    add_model(records, brand="F-One", name="Bandit-S2", season="2021", model_year=2021, source_key="fone_archive", status="review", uncertainty="Official model presence is retained; sizes remain unresolved.")
    write_batch("remaining-cabrinha-fone-2026-10-24.json", "Cabrinha 2016 and F-One models/sizes explicitly named in the supplied research list.", records)


def ozone_naish_slingshot() -> None:
    records: list[dict] = []
    add_model(records, brand="Ozone", name="Enduro V1", season="Unknown", source_key="ozone_enduro", sizes=[4, 6, 7, 8, 9, 10, 12, 14], uncertainty="The official document proves the model and sizes but not a calendar model year.")
    add_model(records, brand="Ozone", name="C4 V6", season="Unknown", source_key="ozone_current", sizes=[6, 7, 8, 9, 10, 11, 12, 14], status="review", uncertainty="Exact manufacturer season remains unresolved.")
    add_model(records, brand="Ozone", name="Reo V7 Ultra-X", season="Current catalogue (checked 2026-10-24)", source_key="ozone_current", sizes=range_sizes(4, 12), uses=["wave"])
    add_model(records, brand="Ozone", name="Zephyr V8 Ultra-X", season="Current catalogue (checked 2026-10-24)", source_key="ozone_current", sizes=[17], uses=["light-wind"])
    for name in ["Edge VT", "Hyperlink V4", "Catalyst V5", "Reflex", "Vortex V2 Ultra-X", "Reo V7", "Alpha V3 Ultra-X", "Ignition V3", "Uno V2", "Mach1", "R1 V5"]:
        add_model(records, brand="Ozone", name=name, season="Current catalogue (checked 2026-10-24)", source_key="ozone_current", status="review", uncertainty="Current model presence is proven; sizes remain unresolved in this batch.")

    for name, season, year, sizes, src in [
        ("Boxer", "2023/2024", None, [2.8, 3.4, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16], "naish_2026"),
        ("Boxer [Q]Series", "2025", 2025, [2.8, 3.4, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16], "naish_2026"),
        ("Hunt [Q]Series", "2026", 2026, [4, 5, 6, 7, 8, 9, 10, 11, 12, 14], "naish_2026"),
        ("Pivot", "2026", 2026, [6, 7, 8, 9, 10, 11, 12, 14], "naish_pivot"),
        ("Psycho [Q]Series", "2026", 2026, [6, 7, 8, 9, 10, 11, 12, 13.5], "naish_2026"),
        ("Pivot NVision", "2026", 2026, [6, 7, 8, 9, 10, 11, 12, 14], "naish_2026"),
    ]:
        add_model(records, brand="Naish", name=name, season=season, model_year=year, source_key=src, sizes=sizes, status="verified" if name == "Pivot" else "review")

    slingshot = [
        ("RPM", 2016, [4.5, 6, 7, 8, 9, 10, 11, 12, 14]), ("Turbine", 2016, [15, 17]),
        ("Machine V1", 2021, range_sizes(5, 12)), ("Machine LW V1", 2021, [15, 17]),
        ("RPX V1", 2021, [4.5, 6, 7, 8, 9, 10, 11, 12, 14]), ("SST V6", 2021, [4, 5, 6, 7, 8, 9, 10, 12]),
        ("UFO V2", 2022, [3, 4, 5, 6, 7, 8, 9, 11]), ("Ghost V2", 2022, [2.5, 4, 6, 8, 10, 12, 15, 17]),
        ("Machine V2", 2023, range_sizes(5, 12)), ("Machine LW V2", 2023, [15, 17]), ("SST V7", 2023, [4, 5, 6, 7, 8, 9, 10, 12]),
    ]
    for name, year, sizes in slingshot:
        add_model(records, brand="Slingshot", name=name, season=str(year), model_year=year, source_key="slingshot", sizes=sizes, status="review", uncertainty="Size list remains flagged for page-level official archive reconfirmation.")
    for name in ["Code NXT", "Code V2"]:
        add_model(records, brand="Slingshot", name=name, season="2025", model_year=2025, source_key="slingshot", status="review", uncertainty="Official model presence is retained; sizes remain unresolved.")
    write_batch("remaining-ozone-naish-slingshot-2026-10-24.json", "Ozone, Naish and Slingshot models named in the supplied research list.", records)


def airush_eleveight_reedin() -> None:
    records: list[dict] = []
    for name in ["Lithium V13", "Ultra V5", "Session V2", "Lift V3", "Razor"]:
        add_model(records, brand="Airush", name=name, season="2023/2024", source_key="airush", status="review", uncertainty="Official model presence is retained; sizes remain unresolved.")
    add_model(records, brand="Airush", name="Lithium Team", season="2025/2026", source_key="airush", sizes=[7, 8, 9, 10, 12, 14, 17], status="review")
    airush_bar = [{
        "targetCategory": "bar", "relation": "recommended",
        "specification": {"manufacturerRecommendedModel": "Team Bar V3"},
        "status": "verified", "source": source("airush_ultra"),
        "notes": "Exact bar season was not established, so this is not linked to a target product version.",
    }]
    add_model(records, brand="Airush", name="Ultra Team DS", season="2025/2026", source_key="airush_ultra", sizes=[7, 8, 9, 10, 12, 14, 17], compatibility=airush_bar, uses=["light-wind", "foil"])

    for name, sizes, uses in [
        ("RS V10", [5, 6, 7, 8, 9, 10, 12, 14, 17], ["all-round"]),
        ("RS+ V4", [6, 7, 8, 9, 10, 12, 14], ["big-air", "freeride"]),
        ("WS V10", [5, 6, 7, 8, 9, 11], ["wave"]),
        ("OS V7", [12, 14], ["foil", "light-wind"]),
        ("PS V10", [4, 6, 8, 10, 12, 14], ["school"]),
    ]:
        add_model(records, brand="Eleveight", name=name, season="Current catalogue (checked 2026-10-24)", source_key="eleveight", sizes=sizes, status="review", uses=uses)
    for name in ["Stratos+", "RS Pro V2", "FS V8"]:
        add_model(records, brand="Eleveight", name=name, season="Current catalogue (checked 2026-10-24)", source_key="eleveight", status="review", uncertainty="Current model presence is proven; sizes remain unresolved.")

    add_model(records, brand="Reedin", name="HyperModel", season="2025", model_year=2025, source_key="reedin", sizes=range_sizes(5, 12), uses=["big-air"])
    add_model(records, brand="Reedin", name="SuperModel HTF", season="2025", model_year=2025, source_key="reedin", status="conflict", uncertainty="Regional manufacturer pages disagree on sizes; no size claims are imported.")
    add_model(records, brand="Reedin", name="SuperModel A.F.T.", season="2026", model_year=2026, source_key="reedin", sizes=range_sizes(5, 12), uses=["all-round"])
    add_model(records, brand="Reedin", name="MasterModel", season="2026", model_year=2026, source_key="reedin", sizes=range_sizes(6, 12), uses=["big-air", "freestyle"])
    add_model(records, brand="Reedin", name="WhisperModel", season="2026", model_year=2026, source_key="reedin", sizes=[13, 15, 17], uses=["light-wind"])
    write_batch("remaining-airush-eleveight-reedin-2026-10-24.json", "Airush, Eleveight and Reedin models named in the supplied research list.", records)


def flysurfer_harlem() -> None:
    records: list[dict] = []
    add_model(records, brand="Flysurfer", name="SPEED5", season="2016", model_year=2016, source_key="flysurfer_downloads", sizes=[6, 9, 12, 15, 18, 21], uncertainty="The 21 m² size is included because it is present in the official manual in addition to the supplied summary.")
    add_model(records, brand="Flysurfer", name="SONIC RACE", season="2017", model_year=2017, source_key="flysurfer_downloads", sizes=[7, 9, 11, 13, 15, 18, 21], uses=["race"])
    current = [
        ("PEAK⁶", [2.5, 4, 5, 6, 8, 11], ["foil"]),
        ("SOUL⁴", [7, 10, 12, 15, 18], ["freeride", "freestyle", "foil"]),
        ("SONIC⁵", [7, 10, 12, 15], ["big-air", "freeride", "foil"]),
        ("ERA²", [6, 7, 8, 9, 10, 12, 14], ["big-air", "freeride", "foil"]),
        ("STOKE⁴", [4, 5, 6, 7, 8, 9, 10, 12], ["wave", "freestyle", "freeride"]),
    ]
    bar_names = {"PEAK⁶": ["CONNECT Control Bar"], "SOUL⁴": ["FUSION Control Bar", "CONNECT Control Bar"], "SONIC⁵": ["FUSION Control Bar"], "ERA²": ["FUSION Control Bar"], "STOKE⁴": ["FORCE Control Bar"]}
    for name, sizes, uses in current:
        compatibility = [{
            "targetCategory": "bar", "relation": "recommended",
            "specification": {"manufacturerRecommendedModels": bar_names[name]},
            "status": "verified", "source": source("flysurfer_current"),
            "notes": "Exact bar season was not established, so this is not linked to a target product version.",
        }]
        add_model(records, brand="Flysurfer", name=name, season="Current catalogue (checked 2026-10-24)", source_key="flysurfer_downloads", sizes=sizes, uses=uses, compatibility=compatibility)
    for name, uses in [("VMG³", ["race"]), ("SUPERSONIC", ["foil", "freeride"]), ("HYBRID²", ["foil", "freeride"]), ("HELI", ["freeride", "big-air", "wave"]), ("INDIE²", ["school", "freeride", "foil"])]:
        add_model(records, brand="Flysurfer", name=name, season="Current catalogue (checked 2026-10-24)", source_key="flysurfer_current", uses=uses, status="review", uncertainty="Current model presence and use cases are proven; sizes remain unresolved in the supplied list.")

    add_model(records, brand="Harlem", name="Force", season="From 2023; exact season unresolved", source_key="harlem", status="review", uncertainty="Model presence from 2023 is retained; exact product season and sizes remain unresolved.")
    for name, sizes, uses, key in [
        ("Thrive V2", range_sizes(5, 13), ["all-round"], "harlem"),
        ("Peak", range_sizes(6, 12), ["big-air"], "harlem"),
        ("Flow", range_sizes(5, 10), ["wave"], "harlem"),
        ("Thrive LiteX", [15, 17], ["light-wind"], "harlem"),
        ("Hadlow Pro", [9, 11, 13], ["freestyle"], "harlem_hadlow"),
    ]:
        compatibility = None
        if name == "Hadlow Pro":
            compatibility = [{
                "targetCategory": "bar", "relation": "recommended",
                "specification": {"manufacturerRecommendedModel": "Hadlow Pro Bar", "lineCount": 5, "lineLengthM": 22},
                "status": "verified", "source": source("harlem_hadlow"),
                "notes": "Exact bar season was not established, so this is not linked to a target product version.",
            }]
        add_model(records, brand="Harlem", name=name, season="Current catalogue (checked 2026-10-24)", source_key=key, sizes=sizes, uses=uses, compatibility=compatibility, status="review" if name in {"Thrive V2", "Peak", "Flow"} else "verified")
    write_batch("remaining-flysurfer-harlem-2026-10-24.json", "FLYSURFER and Harlem models named in the supplied research list.", records)


def main() -> None:
    core_duotone_north()
    cabrinha_fone()
    ozone_naish_slingshot()
    airush_eleveight_reedin()
    flysurfer_harlem()


if __name__ == "__main__":
    main()
