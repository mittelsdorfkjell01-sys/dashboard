"""Build post-freeze comparison results for batch 003."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-003-blind-research.json").read_text(encoding="utf-8"))

regions = {
    "Daymer Bay": ("Cornwall", "available_public"),
    "Gott Bay, Tiree": ("Inner Hebrides / Tiree", "missing"),
    "West Wittering": ("Sussex", "missing"),
    "Llangennith": ("Gower", "missing"),
    "Brandon Bay": ("County Kerry", "missing"),
    "Keel / Trawmore, Achill": ("County Mayo / Achill", "missing"),
    "Inch Strand": ("County Kerry / Dingle", "missing"),
    "Strandhill": ("County Sligo", "missing"),
    "Hoddevik": ("Stad / Nordfjord", "missing"),
    "Borestranda": ("Jæren", "missing"),
    "Sola Beach": ("Jæren", "missing"),
    "Lomsesanden, Lista": ("Lista / Agder", "missing"),
    "Thorlakshofn": ("South Iceland", "missing"),
    "Sandvik, Reykjanes": ("Reykjanes", "missing"),
    "Toro Stenstrand": ("Stockholm Archipelago / Torö", "missing"),
    "Lomma Beach": ("Skåne / Öresund", "missing"),
    "Yyteri": ("Satakunta / Pori", "missing"),
    "Tulliniemi Beach": ("Hanko", "missing"),
    "Ristna Beach": ("Hiiumaa", "missing"),
    "Parnu Beach": ("Pärnu Bay", "missing"),
    "Pavilosta": ("Kurzeme", "missing"),
    "Karosta Beach, Liepaja": ("Liepāja / Kurzeme", "missing"),
    "Nida": ("Curonian Spit", "missing"),
    "Kintai": ("Curonian Lagoon / Nemunas Delta", "missing"),
    "Sventoji": ("Palanga coast", "missing"),
}

images = {
    "Llangennith": "exact_commons_candidates_open",
    "Brandon Bay": "one_exact_commons_candidate_open",
    "Inch Strand": "one_exact_commons_candidate_open",
    "Strandhill": "exact_commons_candidates_open",
    "Hoddevik": "exact_commons_candidates_open",
    "Sola Beach": "one_exact_commons_candidate_open",
    "Parnu Beach": "openverse_generic_candidates_open",
}

corrections = {
    "Gott Bay, Tiree": "Confirm the exact launch and any local zoning; preserve tide and stronger-than-forecast wind warning.",
    "West Wittering": "Store 2XS membership/sign-in, buoy zone, 75 m separation and no-high-tide launch as hard rules.",
    "Llangennith": "Classify world_class; retain rip, tide, wreck and size-dependent level warnings.",
    "Daymer Bay": "Verify the current-year summer kite restriction and define the tide/current-safe launch window.",
    "Brandon Bay": "Classify the cluster world_class; split named reef and beach subspots before any entry is created.",
    "Keel / Trawmore, Achill": "Pin the approved activity area and retain the dangerous-current warning for the eastern half.",
    "Inch Strand": "Publish for surf only until current kite/wind zoning is proven; add daily condition and bathing-zone checks.",
    "Strandhill": "State prominently that it is not a swimming beach and that permanent unpredictable rips are present.",
    "Hoddevik": "Classify world_class and keep cold-water, large-swell rip/closeout and skill-season guidance.",
    "Borestranda": "Attach the exact Jærstrendene protection polygon and current seasonal dates; do not generalize Jæren rules.",
    "Sola Beach": "Resolve the conflicting October/November protection start date against the current legal map.",
    "Lomsesanden, Lista": "Do not count until the exact permitted polygon, current restrictions, winds and hazards are verified.",
    "Thorlakshofn": "Recheck harbour construction and the surviving break footprint with a current local/authority source.",
    "Sandvik, Reykjanes": "Do not count until current access, safety/rescue guidance and an authoritative location source exist.",
    "Toro Stenstrand": "Use marked access/parking and reserve rules; set cold, cobble and fickle wind-swell expectations.",
    "Lomma Beach": "Pin the northern recreation launch outside southern reserve prohibitions and bathing conflicts.",
    "Yyteri": "Attach dune, Munakari seasonal closure and 250 m boat-exclusion rules; distinguish learner and storm conditions.",
    "Tulliniemi Beach": "Map the sport entry outside the swimmer-reserved first section and verify nature-area constraints.",
    "Ristna Beach": "Add cold-water/rapid-depth warnings and confirm any current formal launch restrictions.",
    "Parnu Beach": "Store the designated surf-zone geometry and bathing-season 25 m craft separation.",
    "Pavilosta": "Do not count until current port-channel, launch, protection and discipline-specific evidence is found.",
    "Karosta Beach, Liepaja": "Keep Karosta distinct from central beach; add bathing-zone and white-phosphorus safety guidance.",
    "Nida": "Do not create a town-level spot; identify a legal lagoon launch and separate it from sea-side/protected areas.",
    "Kintai": "Use Kintai Beach, not the observation-tower entry; confirm current conservation-season rules.",
    "Sventoji": "Do not count until the exact current kite zone, conditions, hazards and independent trip value are proven.",
}

coord = {name: "exact_launch_open" for name in corrections}
for name in ("Gott Bay, Tiree", "Daymer Bay", "Keel / Trawmore, Achill", "Inch Strand", "Borestranda", "Sola Beach", "Lomma Beach", "Tulliniemi Beach", "Parnu Beach", "Karosta Beach, Liepaja", "Kintai"):
    coord[name] = "approximate_requires_zone_map"
for name in ("Brandon Bay", "Lomsesanden, Lista", "Thorlakshofn", "Sandvik, Reykjanes", "Pavilosta", "Nida", "Sventoji"):
    coord[name] = "identity_or_launch_open"

rows = []
for item in blind["spots"]:
    name = item["name"]
    rows.append({
        "name": name,
        "verdict": item["blind_verdict"],
        "local_duplicate": False,
        "public_live_duplicate": False,
        "region": regions[name][0],
        "region_status": regions[name][1],
        "coordinate_status": coord[name],
        "image_status": images.get(name, "no_approved_candidate"),
        "priority": "P1" if item["blind_verdict"] != "reject_insufficient_evidence" else "P2",
        "correction": corrections[name],
    })

payload = {
    "batch": "003", "completed_at": "2026-11-10",
    "blind_sha256": "2C250367080D4C6E80CE407B44744F44E1D301363571DD496D666511BA6C9442",
    "comparison_scope": "Public live catalogue (46 published spots), repository seed inventory, and available regions checked after blind freeze.",
    "local_duplicate_limit": "Local PostgreSQL was unavailable because Docker Desktop/Postgres was not running; draft-only rows could not be rechecked.",
    "cloud_duplicate_limit": "No authorized full Cloud/Admin inventory was available; public API covers published rows only.",
    "nearby_note": "Fistral Beach is 19.7 km from Daymer Bay and is a distinct beach/estuary identity, not a duplicate.",
    "spots": rows,
}
assert len(rows) == 25
(ROOT / "batch-003-results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
