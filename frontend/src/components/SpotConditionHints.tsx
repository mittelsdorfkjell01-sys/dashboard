import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { SafetyIcon } from "../lib/icons";
import { buildSpotConditionHints, buildSpotFactCells } from "../lib/spotConditionHints";
import { useOptionalUnits } from "../context/PrefsContext";

/**
 * Safety and location notices, the card the Info column ends on.
 *
 * Three bands, top to bottom:
 *   1. the heading, with a red rule under it — the rule is what marks this as
 *      the block with weight, which is why the warning text below it no longer
 *      repeats a red glyph of its own.
 *   2. the warning itself (editorial safety notice, offshore wind) as plain
 *      text. One factual sentence, no grading, no traffic light. The source
 *      label is gone: everything in this card is either the operator's
 *      editorial notice or the forecast, and naming that per line crowded a
 *      block whose job is to be read, not audited.
 *   3. the plain readings — air, water, bottom — as square cells split across
 *      the full width. Square, not rounded: they are a table foot, not chips
 *      floating in the column.
 *
 * With no warning present the cells stand alone under the heading, which is
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
      className="mt-4 overflow-hidden rounded-card bg-band sm:mt-5"
    >
      <div className="px-3.5 pt-3">
        <div className="flex items-center gap-2">
          <SafetyIcon aria-hidden width={14} height={14} className="shrink-0 text-ink-soft" />
          <h2
            id="spot-condition-hints-title"
            className="text-caption font-semibold uppercase tracking-caps text-ink-soft"
          >
            Sicherheit
          </h2>
        </div>
        {/* The one red mark in this card. It replaces the per-line hazard
            glyph: one rule reads as "this block carries weight" without
            repeating itself for every sentence. */}
        <div aria-hidden className="mt-2 h-0.5 rounded-full bg-danger" />

        {warnings.length > 0 && (
          <ul className="mt-3 space-y-2 pb-3">
            {warnings.map((hint) => (
              <li key={hint.id} className="min-w-0 text-caption leading-snug text-ink">
                {hint.sentence}
              </li>
            ))}
          </ul>
        )}
        {warnings.length === 0 && <div className="pb-3" />}
      </div>

      {cells.length > 0 && (
        <dl
          className="grid divide-x divide-line border-t border-line bg-surface"
          style={{ gridTemplateColumns: `repeat(${cells.length}, minmax(0, 1fr))` }}
        >
          {cells.map((cell) => (
            <div key={cell.id} className="min-w-0 px-3 py-2.5">
              <dt className="text-micro font-medium uppercase tracking-caps text-muted">
                {cell.label}
              </dt>
              <dd className="mt-0.5 break-words text-caption font-medium leading-snug text-ink">
                {cell.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {timing && (
        <p className="border-t border-line px-3.5 py-2 text-micro leading-snug text-muted">
          Vorhersage · {timing}
        </p>
      )}
    </section>
  );
}
