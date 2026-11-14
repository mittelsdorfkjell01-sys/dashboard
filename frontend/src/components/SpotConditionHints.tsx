import { useState } from "react";
import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { InfoIcon, SafetyIcon } from "../lib/icons";
import { buildSpotConditionHints, buildSpotFactCells } from "../lib/spotConditionHints";
import { useOptionalUnits } from "../context/PrefsContext";

/**
 * Safety and location notices, the card the Info column ends on.
 *
 * No panel, no fill, no heading: the block stands on the page like the
 * description above it, flush with the same left edge.
 *   1. The warnings (editorial safety notice, offshore wind) lead — each one
 *      factual sentence, marked by a single red hazard glyph. No grading, no
 *      traffic light, no per-line source label, and no word "Sicherheit" over
 *      the top: the glyph already says it. Small type on a narrow measure, so
 *      it reads as a note, not as a second paragraph.
 *   2. The plain readings — air, water, bottom — follow, set apart and a step
 *      larger, because they are what people come to look up.
 *   3. The forecast's validity is folded away behind a small marker in the
 *      bottom right corner. It belongs on the page — a reading without its
 *      timestamp is a claim without a date — but nobody reads it before the
 *      reading it describes, so it waits until asked for.
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
  // Declared before the early return below: hooks must run in the same order
  // on every render, and this component bails out when it has nothing to show.
  const [timingOpen, setTimingOpen] = useState(false);
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
        <ul className="space-y-1.5">
          {warnings.map((hint) => (
            <li key={hint.id} className="min-w-0">
              {/* Flush with the column's left edge, like the title and the
                  description above it — the block is a note in that column,
                  not a centred banner across it. The glyph is set inline with
                  the sentence so the text keeps that edge instead of being
                  pushed in by a hanging icon. The measure sits on the
                  paragraph, because `ch` resolves against the element's own
                  font size — on a wrapper it would be read at the inherited
                  14px, three times wider than meant. */}
              <p className="min-w-0 max-w-[46ch] text-micro leading-snug text-ink-soft">
                <SafetyIcon
                  aria-hidden
                  width={12}
                  height={12}
                  className="mr-1 inline-block shrink-0 translate-y-[1px] text-danger"
                />
                {hint.sentence}
              </p>
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
        <div className="mt-2 flex flex-col items-end gap-1">
          <button
            type="button"
            onClick={() => setTimingOpen((open) => !open)}
            aria-expanded={timingOpen}
            aria-controls="spot-forecast-validity"
            className="grid h-6 w-6 place-items-center rounded-full text-muted transition-colors hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            {/* Not the red exclamation mark: that glyph marks a hazard on this
                page, and spending it on a timestamp would teach people to
                ignore it. A neutral marker, same size, no colour. */}
            <InfoIcon aria-hidden width={13} height={13} />
            <span className="sr-only">
              {timingOpen ? "Gültigkeit der Vorhersage ausblenden" : "Gültigkeit der Vorhersage anzeigen"}
            </span>
          </button>
          {timingOpen && (
            <p
              id="spot-forecast-validity"
              className="text-right text-micro leading-snug text-muted"
            >
              Vorhersage · {timing}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
