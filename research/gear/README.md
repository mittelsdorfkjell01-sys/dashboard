# Gear research staging

This directory is the review boundary between research and catalogue data.
Research is not production-ready merely because it is present here.

## Workflow

1. The Gear Researcher records source-backed, field-level claims in `staging/`.
2. A reviewer checks product identity, manufacturer-stated season, size and
   colour scope, claim status, uncertainty and image/technical-reference rights.
3. Validate an accepted batch with `python -m scripts.import_gear_staging
   research/gear/staging/BATCH.json`. This performs a transactional dry-run.
4. Import the reviewed batch with the same command plus `--apply`. The importer
   only adds data, skips exact duplicates and stops on conflicting existing
   claims. Never edit a shipped migration or bypass this review boundary.
5. Store compatibility and use profiles separately from technical properties.
   A compatibility record links a product to a category or exact product;
   a use profile combines sport, discipline, condition and suitability.
   Use `targetProduct` with brand, name and season when an official source proves
   the exact compatible product. Otherwise keep the category and system details
   explicit without guessing a product generation.
6. Do not store numeric wind ranges for kite sizes. Describe suitability only
   with the qualitative use-profile conditions such as `light_wind`,
   `strong_wind` or `waves` and retain the supporting source.

## Property contract

Claim names, value types, scopes, units and controlled vocabularies live in
`app/gear/properties.py`. Add or review a property there before using it in a
staging batch. Unknown fields and non-canonical units are rejected rather than
silently entering the catalogue.

Every file must have an accepted `reviewStatus`, `checkedAt`, a rights note and
at least one record. Every claim needs a source, either directly or inherited
from its record. Prefer a structured source object:

```json
{
  "url": "https://manufacturer.example/product",
  "title": "Official product page",
  "publisher": "Manufacturer",
  "type": "manufacturer_page",
  "checkedAt": "2026-10-23T12:00:00Z",
  "rights": "Facts only; no imagery copied."
}
```

`coverage.json` tracks the 2016-to-current research queue. A blank
`latestOfficialSeason` means that no official source has yet established the
brand's current published season; it must not be inferred from today's year.

## Next research priority

1. Complete the official 2016-present model timeline for CORE, Duotone and
   F-One, starting with the pilot families and explicitly resolving gaps.
2. Flysurfer and Ozone, because official manuals and line plans can exercise
   foil-kite and size-specific technical evidence.
3. North, Cabrinha, Naish and Slingshot.
4. Airush, Eleveight, Reedin and Harlem.

Every batch stays deliberately small enough for field-level review.
