"""Build post-freeze comparison results for batch 011."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-011-blind-research.json").read_text(encoding="utf-8"))
images = json.loads((ROOT / "batch-011-blind-image-candidates.json").read_text(encoding="utf-8"))

country_region = {"UA": "Ukraine / candidate oblast", "MD": "Moldova / candidate district", "GE": "Georgia / candidate region"}
rows = []
for item, image in zip(blind["spots"], images["spots"], strict=True):
    image_count = sum(len(values) for values in image["providers"].values())
    rows.append({
        "name": item["name"], "verdict": item["blind_verdict"], "blind_verdict": item["blind_verdict"],
        "local_duplicate": False, "public_live_duplicate": False, "duplicate_of": None,
        "region": country_region[item["country"]], "region_status": "missing",
        "coordinate_status": "identity_or_launch_open" if item["blind_verdict"] in {"hold_for_more_research", "reject_insufficient_evidence"} else "approximate_requires_zone_map",
        "image_status": "unreviewed_candidates_not_approved" if image_count else "no_approved_candidate",
        "image_candidate_count": image_count,
        "priority": "P1" if item["blind_verdict"] in {"accept_as_worth_trip", "accept_after_correction", "hold_for_more_research"} else "P2",
        "correction": item["access_rules"],
    })

payload = {
    "batch": "011", "completed_at": "2026-11-10",
    "blind_sha256": "E83266AC3DA796308B42E2C89ACEEB390D38EBD394FD22E2414A865DB2800618",
    "comparison_scope": "Public live catalogue (46 published spots), repository seed inventory, public regions and prior completed batches checked after blind freeze.",
    "local_duplicate_limit": "Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
    "cloud_duplicate_limit": "No authorized full Cloud/Admin inventory was available.",
    "nearby_note": "No exact public-live, seed, prior-batch or within-batch duplicate was found. Ukrainian candidates remain non-publishable while current travel warnings and occupation/war constraints apply.",
    "within_batch_duplicate": None,
    "spots": rows,
}
assert len(rows) == 25
(ROOT / "batch-011-results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
