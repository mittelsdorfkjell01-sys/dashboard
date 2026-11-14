import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";

/**
 * Whether a spot works for foiling.
 *
 * Foiling is not simply "the same sport with a different board": it needs
 * enough water depth, a workable launch area and often a different wind range.
 * So the catalogue records its own suitability for it and — this is the point —
 * never derives it from the main sport. A spot that is proven for fin
 * windsurfing says nothing about whether a foil clears the bottom there.
 *
 * It is ONE category, not one per sport. What a foil needs is a property of the
 * water, not of whether the rider holds a sail or a bar, so the page shows a
 * single line for a spot that lists windsurfing, kitesurfing or both.
 *
 * Until an editor has reviewed a variant it reads "unbekannt". That is a
 * statement about our review, not about the spot: unknown is not unsuitable.
 * It is deliberately shown rather than hidden, because a missing line would
 * leave a foiler guessing, and guessing here can mean hitting the bottom.
 *
 * No colour coding, no score — a label and a word, matching the house rule that
 * guidance is factual text, never a traffic light.
 */

/** The one foil key, and the sports it concerns (mirrors app/admin/constants.py).
 *  `wing` is its own sport (Wingfoilen is always foiled) and `surf` is left out
 *  — Surf-Foil is not silently folded in here. */
const FOIL_VARIANT = "foil";
const FOIL_SPORTS = ["windsurf", "kitesurf"];

const SUITABILITY_LABEL: Record<string, string> = {
  geeignet: "geeignet",
  eingeschraenkt: "eingeschränkt",
  ungeeignet: "ungeeignet",
  unbekannt: "ungeprüft",
};

export function variantSuitability(spot: Spot, variantKey: string): string {
  const stored = spot.variantConditions?.[variantKey]?.suitability;
  return stored && stored in SUITABILITY_LABEL ? stored : "unbekannt";
}

export default function SpotVariants({ spot }: { spot: Spot }) {
  const concerns = (spot.sports ?? []).some((sport) => FOIL_SPORTS.includes(sport));
  if (!concerns) return null;
  const suitability = variantSuitability(spot, FOIL_VARIANT);

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
      <span className="inline-flex items-baseline gap-1.5 text-caption">
        <span className="font-medium text-ink-soft">Foil</span>
        <span className={suitability === "unbekannt" ? "text-muted" : "text-ink"}>
          {SUITABILITY_LABEL[suitability]}
        </span>
      </span>
      {suitability === "unbekannt" && (
        <Link
          to="/fragen#spots"
          className="text-caption text-muted underline underline-offset-4 hover:text-ink"
        >
          Was heißt ungeprüft?
        </Link>
      )}
    </div>
  );
}
