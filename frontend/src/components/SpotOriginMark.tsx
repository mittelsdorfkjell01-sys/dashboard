import type { Spot } from "../lib/types";
import { EditorialMarkIcon } from "../lib/icons";
import { useSpotOriginsMixed } from "../context/SpotOriginContext";

/**
 * The one mark that says "we entered this spot ourselves": the house teardrop
 * in miniature, next to the spot name on tiles and on the detail page.
 *
 * It is deliberately not a check badge. A check reads as a verification claim,
 * and that would be untrue here — a community spot passes the same admin
 * approval, so the difference is authorship, not review. The house mark says
 * exactly that and nothing more: muted, no background, no accent colour, no
 * second mark for community spots (their credit is the contributor's name in
 * `SpotOriginLine`).
 *
 * Renders nothing while the catalogue is all ours — see
 * `useSpotOriginsMixed`.
 */
export default function SpotOriginMark({
  origin,
  className = "",
}: {
  origin?: Spot["origin"];
  className?: string;
}) {
  const mixed = useSpotOriginsMixed();
  if (!mixed || origin !== "editorial") return null;
  return (
    <EditorialMarkIcon
      role="img"
      aria-label="Von der Redaktion erfasst"
      className={`shrink-0 text-muted ${className}`}
      width="0.78em"
      height="0.78em"
    />
  );
}

/**
 * The written-out counterpart to the mark, for the foot of the spot page: who
 * entered this spot. Always rendered, mixed catalogue or not — unlike the mark
 * it is informative on its own, and it is the place the mark's tooltip points
 * at.
 */
export function SpotOriginLine({ spot, className = "" }: { spot: Spot; className?: string }) {
  const text =
    spot.origin === "community"
      ? spot.contributorName
        ? `Dieser Spot wurde von ${spot.contributorName} eingetragen und als Community-Beitrag übernommen.`
        : "Dieser Spot wurde von der Community eingetragen und als Community-Beitrag übernommen."
      : "Dieser Spot wurde von der Redaktion erfasst.";
  return <p className={`text-caption text-muted ${className}`}>{text}</p>;
}
