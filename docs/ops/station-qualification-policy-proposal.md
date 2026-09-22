# Pilot policy for station qualification — decision proposal

| Field | Value |
| --- | --- |
| Proposed policy ID | `station-pilot-policy-proposal-2026-09-v1` |
| Status | **PROPOSAL — NOT APPROVED — MUST NOT BE APPLIED** |
| Applies to | one stable station epoch and one explicitly approved purpose |
| Evidence boundary | operational capture evidence only; no backfill or legacy timestamps |
| Holdout boundary | freeze the approved policy version before inspecting holdout results |

This document is a signature-ready decision record, not an active runtime
policy. No number below is approved. `QualificationPolicy` stays unconfigured,
all purpose approvals remain manual, and the LiveWind gate stays closed until
the authorisation section is completed and an immutable approved policy version
is published separately. Do not rename this proposal to an approved version or
copy its values into runtime configuration without that decision.

## Measurement definitions

- **Stable epoch:** one `weather_station_epochs` row whose configuration hash
  does not change during the review window. A metadata change starts or proposes
  another epoch; evidence is never combined across epochs.
- **Operational window:** `[window_start, window_end]` in UTC, ending at the
  dossier cutoff. Only rows with `availability_class=captured_operationally`, a
  real `first_seen_at`, and that epoch ID count. Backfills and
  `availability_unproven` rows remain visible but contribute neither numerator
  nor elapsed days.
- **Expected intervals:** inclusive scheduled slots in the operational window,
  using the provider's reviewed station-epoch interval. If that interval is
  unknown, completeness is unknown and strict roles fail closed.
- **Capture completeness numerator:** distinct observation times received for
  that epoch within the expected slots. Duplicate deliveries count once.
  Intrinsic QC exclusions remain in the capture numerator and are assessed
  separately; this prevents provider delivery quality and sensor quality from
  hiding each other.
- **Receipt latency:** `received_at - observed_at` for operational rows with
  both real UTC timestamps. Negative, missing, backfilled or unproven values are
  excluded from the quantile and separately counted as blockers.
- **QC exclusion share:** rows excluded for intrinsic sensor/provider reasons
  divided by all operationally received rows. Governance reasons such as an
  unreviewed identity or missing approval are reported separately and do not
  masquerade as sensor QC.
- **Independent group:** a manually confirmed correlation group after physical
  identity and sensor relationships were reviewed. ICAO, WIGOS, proximity or
  measured correlation alone proposes a review; it never confirms a group.

## Proposed decisions — every threshold is unapproved

| Decision | Proposed measurable rule — **not approved** | Roles | Insufficient/unknown evidence |
| --- | --- | --- | --- |
| Minimum duration | At least **28 real elapsed UTC days** between the first and last qualifying operational capture of the same stable epoch. The window must contain expected intervals throughout; a short burst on 28 calendar labels is insufficient. | `residual_source`, `holdout_input`, `holdout_target`; monitoring may be reviewed earlier with an explicit limitation. | Strict roles blocked. Report remaining real days; never fill gaps with backfills. |
| Completeness | Capture completeness over the same 28-day epoch window: at least **90%** for `residual_source` and `holdout_input`, and **95%** for `holdout_target`. | As stated; monitoring is descriptive until separately decided. | Unknown provider interval or denominator blocks strict roles. |
| Live freshness | At analysis cutoff, the newest accepted input observation must be no more than **30 minutes** old. | Any future live input use. | Exclude the station from that analysis; do not reuse the last value indefinitely. |
| Receipt latency | Proposed operational latency requirement: `p95(received_at-observed_at) <= 30 minutes` over the same window. Report p50/p90/p95/p99 and the excluded timestamp count. | `residual_source`, `holdout_input`, `holdout_target`. | Missing/negative/unproven timestamps block strict roles. |
| Outage and recovery | Any interior gap greater than **6 hours** pauses the live role. Proposed recovery requires **24 subsequent real hours** of stable operational capture with no new gap above the reviewed interval tolerance. | Live input roles; monitoring remains visible as degraded. | Role remains paused. Recovery never backdates eligibility. |
| QC exclusions | More than **5%** intrinsic QC exclusions among received operational measurements requires a documented root-cause review. This is an investigation trigger, not permission to discard inconvenient rows. | All roles. | Strict roles remain blocked until the cause and disposition are signed. |
| Wind measurement height | Unknown individual wind-sensor height may be accepted for clearly labelled `monitoring`; it is prohibited for `residual_source`, `holdout_input` and `holdout_target`. Station elevation or a nominal WMO height is not a substitute. | As stated. | Strict roles blocked; retain `measurement_height_unknown` visibly. |
| Independent holdout inventory | At least **10 manually reviewed independent holdout target groups**, plus separate independent input groups that remain after each leave-one-group-out exclusion. The same physical/correlation group cannot satisfy both sides of one case. | Holdout verification only. | Holdout gate blocked even if ten target records exist without usable foreign inputs. |
| Subgroup regression | Predeclare country, terrain, coast/inland, season and wind sector. Proposed block if candidate u/v-MAE worsens by more than **0.15 m/s**, but only for a subgroup with a preapproved independent sample/day floor and confidence method. | Candidate verification and later Canary decision. | An underpowered subgroup is `not_demonstrated`, never passed. No threshold tuning against viewed holdouts. |

## Role decision matrix

Every approval binds station ID, epoch ID, dossier hash, approved policy version,
group version, actor, reason and decision time. A later approval cannot make an
earlier observation, model asset, residual or holdout case eligible.

| Role | Minimum evidence before a human may approve |
| --- | --- |
| `monitoring` | provider/license reviewed, stable epoch identified, timestamps and limitations visible; unknown measurement height must be stated explicitly |
| `residual_source` | reviewed physical/correlation groups, official individual measurement height, proposed duration/completeness/latency/QC/outage decisions satisfied under an approved policy |
| `holdout_input` | all residual-source requirements plus independence from the held-out target after duplicate/dependency exclusion |
| `holdout_target` | all strict requirements, proposed 95% completeness, and membership in the manually reviewed independent target inventory |

## Technical reachability review

The thresholds must be evaluated only from capture and latency evidence in an
immutable epoch dossier. Holdout accuracy, candidate uplift and later LiveWind
quality are forbidden inputs to the threshold decision. Before signing, the
reviewer records distributions by provider and station epoch and answers:

1. Can DWD and DMI technically meet the proposed completeness and p95 latency?
2. Are provider publication delays distinguishable from runner outages?
3. Does the expected-interval denominator reflect a documented provider cadence?
4. Are pause/recovery events and excluded timestamp rows visible in the dossier?
5. Are at least ten independent target groups left with separate input groups?

If any answer is unknown, the affected threshold remains undecided and the
corresponding role stays closed.

## Required authorisation — intentionally blank

| Approval field | Required value |
| --- | --- |
| Final immutable policy version | ______________________________ |
| Authorised decision owner | ______________________________ |
| Independent technical reviewer | ______________________________ |
| Decision timestamp (UTC) | ______________________________ |
| Effective capture cutoff (UTC) | ______________________________ |
| Approved changes from this proposal | ______________________________ |
| Rationale and evidence dossier set | ______________________________ |
| Decision-owner signature | ______________________________ |
| Technical-review signature | ______________________________ |

Until every required field is complete and the approved artifact is frozen,
the correct system state is: `qualification_policy_unconfigured`, station
purpose approvals outstanding, holdout gate closed, Canary not started.
