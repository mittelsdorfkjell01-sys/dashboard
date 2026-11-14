import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { SafetyIcon } from "../lib/icons";
import { buildSpotConditionHints, buildSpotFactCells } from "../lib/spotConditionHints";
import { useOptionalUnits } from "../context/PrefsContext";

/**
 * Safety and location notices, the card the Info column ends on.
 *
 * No panel, no fill, no rules (DESIGN.md, The No Tile Background Rule): the
 * block stands on the page like the description above it. Three quiet lines,
 * top to bottom:
 *   1. a small "Sicherheit" eyebrow,
 *   2. the warnings (editorial safety notice, offshore wind), each one factual
 *      sentence marked by a single red hazard glyph. No grading, no traffic
 *      light, and no per-line source label: everything here is either the
 *      operator's notice or the forecast, and naming that on every line
 *      crowded a block whose job is to be read, not audited.
 *   3. the plain readings — air, water, bottom — as label/value pairs on one
 *      wrapping line.
 *
 * With no warning present the readings stand alone under the eyebrow, which is
 * the honest state for a spot nobody has flagged.
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
      aria-labelledby="spot-condition-hints-title"
      aria-live="polite"
      className="mt-4 sm:mt-5"
    >
      <div className="flex items-center gap-1.5">
        <SafetyIcon aria-hidden width={12} height={12} className="shrink-0 text-muted" />
        <h2
          id="spot-condition-hints-title"
          className="text-micro font-medium uppercase tracking-caps text-muted"
        >
          Sicherheit
        </h2>
      </div>

      {warnings.length > 0 && (
        <ul className="mt-1.5 space-y-1.5">
          {warnings.map((hint) => (
            <li key={hint.id} className="flex min-w-0 gap-2">
              {/* The one red mark on the page, and it is this small: a glyph on
                  the sentence that warrants it. The block used to carry a
                  full-width red rule and a tinted panel, which shouted the
                  same thing three times over. */}
              <SafetyIcon aria-hidden width={13} height={13} className="mt-0.5 shrink-0 text-danger" />
              <p className="min-w-0 text-caption leading-snug text-ink-soft">{hint.sentence}</p>
            </li>
          ))}
        </ul>
      )}

      {cells.length > 0 && (
        <dl className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
          {cells.map((cell) => (
            <div key={cell.id} className="flex min-w-0 items-baseline gap-1.5">
              <dt className="text-micro font-medium uppercase tracking-caps text-muted">
                {cell.label}
              </dt>
              <dd className="min-w-0 break-words text-caption font-medium leading-snug text-ink">
                {cell.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {timing && (
        <p className="mt-1.5 text-micro leading-snug text-muted">Vorhersage · {timing}</p>
      )}
    </section>
  );
}
