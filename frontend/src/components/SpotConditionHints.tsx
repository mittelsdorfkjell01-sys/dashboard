import { useState } from "react";
import { usePresence } from "../lib/usePresence";
import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { InfoIcon, SafetyIcon } from "../lib/icons";
import { buildSpotConditionHints, buildSpotFactCells } from "../lib/spotConditionHints";
import { useOptionalUnits } from "../context/PrefsContext";

/**
 * Safety and location notices, the card the Info column ends on.
 *
 * No panel, no fill, no heading. The block steps in from the body's left edge
 * — it is a note about the column above it, not another paragraph in it — and
 * the hazard glyph sits in the space that step opens up.
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
  const validity = usePresence(timingOpen, 150);
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
              {/* Indented, not flush: the block is a note *about* the column
                  above it, so it steps in from the body's left edge instead of
                  starting on it, and the hazard glyph sits in the space that
                  step opens up. The text keeps a single left edge of its own —
                  it hangs beside the glyph rather than wrapping under it.

                  The measure sits on the paragraph, because `ch` resolves
                  against the element's own font size; on a wrapper it would be
                  read at the inherited 14px, three times wider than meant. */}
              <div className="flex min-w-0 gap-2 pl-6 sm:pl-8">
                <SafetyIcon
                  aria-hidden
                  width={15}
                  height={15}
                  className="mt-px shrink-0 text-danger"
                />
                <p className="min-w-0 max-w-[46ch] text-micro leading-snug text-ink-soft">
                  {hint.sentence}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {cells.length > 0 && (
        /* Set apart from the warning above: these are plain readings of the
           place, not a caution, and at 12px they are the most legible thing in
           the block — which is right, because they are what gets looked up. */
        <dl className="mt-3 flex flex-wrap items-baseline gap-x-5 gap-y-1 pl-6 sm:pl-8">
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
            // 44px target around the 24px mark; the negative margin keeps the
            // glyph exactly where it was.
            className="-m-2.5 grid h-11 w-11 place-items-center rounded-full text-muted transition-colors hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            {/* Not the red exclamation mark: that glyph marks a hazard on this
                page, and spending it on a timestamp would teach people to
                ignore it. A neutral marker, same size, no colour. */}
            <InfoIcon aria-hidden width={13} height={13} />
            <span className="sr-only">
              {timingOpen ? "Gültigkeit der Vorhersage ausblenden" : "Gültigkeit der Vorhersage anzeigen"}
            </span>
          </button>
          {validity.mounted && (
            <p
              id="spot-forecast-validity"
              data-shown={validity.shown}
              // Fades in and settles 4px down (chosen 2026-11-24); see .swd-drop.
              className="swd-drop text-right text-micro leading-snug text-muted"
            >
              Vorhersage · {timing}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
