import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";

/**
 * Foil variants of the sports a spot lists.
 *
 * Foiling is not simply "the same sport with a different board": it needs
 * enough water depth, a workable launch area and often a different wind range.
 * So the catalogue records a separate suitability per variant and — this is the
 * point — never derives it from the main sport. A spot that is proven for fin
 * windsurfing says nothing about whether a foil clears the bottom there.
 *
 * Until an editor has reviewed a variant it reads "unbekannt". That is a
 * statement about our review, not about the spot: unknown is not unsuitable.
 * It is deliberately shown rather than hidden, because a missing line would
 * leave a foiler guessing, and guessing here can mean hitting the bottom.
 *
 * No colour coding, no score — a label and a word, matching the house rule that
 * guidance is factual text, never a traffic light.
 */

/** The foil variant each sport can carry (mirrors app/admin/constants.py). */
const FOIL_VARIANT: Record<string, { key: string; label: string }> = {
  windsurf: { key: "windsurf:foil", label: "Windfoil" },
  kitesurf: { key: "kitesurf:foil", label: "Kitefoil" },
};

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
  const rows = (spot.sports ?? [])
    .map((sport) => FOIL_VARIANT[sport])
    .filter((variant): variant is { key: string; label: string } => Boolean(variant))
    .map((variant) => ({ ...variant, suitability: variantSuitability(spot, variant.key) }));

  if (!rows.length) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {rows.map((row) => (
        <span key={row.key} className="inline-flex items-baseline gap-1.5 text-caption">
          <span className="font-medium text-ink-soft">{row.label}</span>
          <span className={row.suitability === "unbekannt" ? "text-muted" : "text-ink"}>
            {SUITABILITY_LABEL[row.suitability]}
          </span>
        </span>
      ))}
      {rows.some((row) => row.suitability === "unbekannt") && (
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
