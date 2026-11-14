import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { SafetyIcon } from "../lib/icons";
import { buildSpotConditionHints, buildSpotFactCells } from "../lib/spotConditionHints";
import { useOptionalUnits } from "../context/PrefsContext";

/**
 * Safety and location notices, the card the Info column ends on.
 *
 * No panel, no fill, no heading (DESIGN.md, The No Tile Background Rule): the
 * block stands on the page like the description above it.
 *   1. The warnings (editorial safety notice, offshore wind) lead — each one
 *      factual sentence, marked by a single red hazard glyph. No grading, no
 *      traffic light, no per-line source label, and no word "Sicherheit" over
 *      the top: the glyph already says it. Small type on a narrow measure, so
 *      it reads as a note, not as a second paragraph.
 *   2. The plain readings — air, water, bottom — follow, set apart and a step
 *      larger, because they are what people come to look up.
 *   3. The forecast's validity sits last and smallest.
 *
 * With no warning present the readings stand alone, which is the honest state
 * for a spot nobody has flagged. The region keeps the accessible name
 * "Sicherheit" although nothing on screen says it.
 */
export default function SpotConditionHints({
  spot,
  forecast,
}: {
  spot: Spot;
  forecast?: ForecastSummaryRead | null;
}) {
  // Temperature follows the visitor's unit preference like every other reading.
  const units = useOptionalUnits();
  const hints = buildSpotConditionHints(spot, forecast, units.temp);
  const cells = buildSpotFactCells(spot, forecast, units.temp);

  const warnings = hints.filter((hint) => hint.kind === "safety" || hint.kind === "wind");
  if (warnings.length === 0 && cells.length === 0) return null;

  const timing = hints.find((hint) => hint.sourceLabel === "Vorhersage" && hint.timing)?.timing;

  return (
    <section
      aria-label="Sicherheit"
      aria-live="polite"
      className="mt-4 sm:mt-5"
    >
      {warnings.length > 0 && (
        /* No heading any more: a red hazard glyph and one factual sentence say
           what this is, and a word above them only repeated it. The text is set
           at the same small size as the spec tiles and held to a narrow
           measure, so it reads as a note beside the description rather than a
           second paragraph competing with it. */
        <ul className="space-y-1.5">
          {warnings.map((hint) => (
            <li key={hint.id} className="flex min-w-0 gap-1.5">
              <SafetyIcon aria-hidden width={12} height={12} className="mt-0.5 shrink-0 text-danger" />
              {/* The measure sits on the paragraph, not the row: `ch` resolves
                  against the element's own font size, and on the row it would
                  be read at the inherited 14px — three times wider than meant. */}
              <p className="min-w-0 max-w-[46ch] text-micro leading-snug text-ink-soft">{hint.sentence}</p>
            </li>
          ))}
        </ul>
      )}

      {cells.length > 0 && (
        /* Set apart from the warning above: these are plain readings of the
           place, not a caution, and at 12px they are the most legible thing in
           the block — which is right, because they are what gets looked up. */
        <dl className="mt-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
          {cells.map((cell) => (
            <div key={cell.id} className="flex min-w-0 items-baseline gap-1.5">
              <dt className="text-micro font-medium uppercase tracking-caps text-muted">
                {cell.label}
              </dt>
              <dd className="min-w-0 break-words text-caption leading-snug text-ink">
                {cell.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {timing && (
        /* The smallest step the scale has, bottom left: provenance belongs on
           the page, but nobody reads it before the reading it describes. */
        <p className="mt-2 text-left text-micro leading-snug text-muted">Vorhersage · {timing}</p>
      )}
    </section>
  );
}
