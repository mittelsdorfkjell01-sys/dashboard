// Builds the spot-detail "Steckbrief" (category facts) and the Facilities list
// from the backend spot record. Category axes use German labels; unknown
// facilities (a kind absent from the map) are hidden — never shown as "unknown".

import type { Facility, SpotFact } from "./types";
import type { Spot } from "./types";
import type { FacilityMap } from "./api";
import {
  FACILITY_KINDS,
  facilityLabel,
  levelLabel,
  sportLabel,
  styleList,
  waterCharacterLabel,
} from "./labels";

/** The three category axes (+ sports) as a key/value character sheet. */
export function spotFactsFrom(spot: Spot): SpotFact[] {
  const facts: SpotFact[] = [];
  if (spot.sports && spot.sports.length)
    facts.push({ label: "Sportarten", value: spot.sports.map(sportLabel).join(", ") });
  if (spot.level && spot.level.length)
    facts.push({ label: "Level", value: spot.level.map(levelLabel).join(", ") });
  if (spot.waterCharacter && spot.waterCharacter.length)
    facts.push({
      label: "Wasserart",
      value: spot.waterCharacter.map(waterCharacterLabel).join(", "),
    });
  if (spot.style && spot.style.length)
    facts.push({ label: "Fahrstil", value: styleList(spot.style) });
  return facts;
}

/** All five facility kinds, always, in canonical order — a kind absent from
 *  the map is "unbekannt" (available: null), not hidden. Hiding it would read
 *  as "definitely not here" when really nobody has checked yet. */
export function facilitiesFromMap(map?: FacilityMap | null): Facility[] {
  return FACILITY_KINDS.map((kind) => {
    const entry = map?.[kind];
    if (!entry) {
      return { kind, title: facilityLabel(kind), note: "Keine Angabe", available: null };
    }
    return {
      kind,
      title: facilityLabel(kind),
      note: entry.note ?? (entry.available ? "Vorhanden" : "Nicht vorhanden"),
      available: entry.available,
    };
  });
}
