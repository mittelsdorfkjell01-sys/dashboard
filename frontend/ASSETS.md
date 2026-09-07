# Asset provenance

Production images, fonts, logos, and other media must have documented usage
rights before they are committed or deployed. Repository access alone does not
grant reuse rights.

## Current asset groups

| Path | Purpose | Rights record |
|---|---|---|
| `public/hero-*` | Generated delivery variants for landing heroes | Owner verification required |
| `hero-src/hero-*` | High-resolution hero source files | Owner verification required |
| `public/fonts/Poppins-*` | Self-hosted UI font files | Verify against the upstream font license |
| `public/fonts/MADEMountain-*` | Wordmark font | Confirm the purchased/downloaded license permits web embedding |

## Required record for new assets

Record the source URL or supplier, creator, acquisition date, license, allowed
commercial uses, modification rights, attribution text, and the person who
verified the rights. Do not store purchase receipts or personal account details
in Git; keep those in the private business record and reference only its ID.
