import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { GroundIcon, SafetyIcon, TemperatureIcon, WindIcon } from "../lib/icons";
import { buildSpotConditionHints } from "../lib/spotConditionHints";
import { useOptionalUnits } from "../context/PrefsContext";

/**
 * Safety and location notices under the description.
 *
 * The block separates the two things it carries, because they are not the
 * same claim and must not read as one list:
 *   - a *warning* (the editorial safety notice, offshore wind) leads, on its
 *     own line, marked by the red hazard glyph and a red rule on the left
 *     edge. One factual sentence, no grading, no traffic light.
 *   - *facts* (temperature, bottom) follow as quiet chips. They describe the
 *     spot, they do not warn about it, so they carry no colour at all.
 *
 * With no warning present the chips stand alone and the block stays visually
 * silent — which is the honest state for a spot nobody has flagged.
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
  if (!hints.length) return null;
  const forecastTiming = hints.find(
    (hint) => hint.sourceLabel === "Vorhersage" && hint.timing,
  )?.timing;

  const warnings = hints.filter((hint) => hint.kind === "safety" || hint.kind === "wind");
  const facts = hints.filter((hint) => hint.kind !== "safety" && hint.kind !== "wind");

  const sourceNote = (label: string) =>
    label === "Redaktioneller Sicherheitshinweis"
      ? "Redaktion"
      : label === "Geprüftes Spotprofil"
        ? "Spotprofil"
        : "Vorhersage";

  return (
    <section
      aria-labelledby="spot-condition-hints-title"
      aria-live="polite"
      className="mt-4 rounded-card bg-band px-3.5 py-3 sm:mt-5"
    >
      <div className="flex items-center gap-2 text-ink">
        <SafetyIcon aria-hidden width={14} height={14} className="shrink-0 text-ink-soft" />
        <h2
          id="spot-condition-hints-title"
          className="text-caption font-semibold uppercase tracking-caps text-ink-soft"
        >
          Sicherheit
        </h2>
      </div>

      {warnings.length > 0 && (
        <ul className="mt-2.5 space-y-2">
          {warnings.map((hint) => (
            <li
              key={hint.id}
              className="flex min-w-0 items-start gap-2.5 rounded-card border-l-2 border-danger bg-surface px-3 py-2.5"
            >
              <SafetyIcon aria-hidden width={14} height={14} className="mt-0.5 shrink-0 text-danger" />
              <p className="min-w-0 text-caption leading-snug text-ink">
                {hint.sentence}
                <span className="ml-1.5 whitespace-nowrap text-micro text-muted">
                  · {sourceNote(hint.sourceLabel)}
                </span>
              </p>
            </li>
          ))}
        </ul>
      )}

      {facts.length > 0 && (
        <ul className={`flex flex-wrap gap-1.5 ${warnings.length > 0 ? "mt-2.5" : "mt-2"}`}>
          {facts.map((hint) => {
            const Icon = hint.kind === "temperature" ? TemperatureIcon : hint.kind === "wind" ? WindIcon : GroundIcon;
            return (
              <li
                key={hint.id}
                className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1"
              >
                <Icon aria-hidden width={13} height={13} className="shrink-0 text-ink-soft" />
                <span className="min-w-0 break-words text-caption leading-snug text-ink-soft">
                  {hint.sentence}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {forecastTiming && (
        <p className="mt-2 text-micro leading-snug text-muted">Vorhersage · {forecastTiming}</p>
      )}
    </section>
  );
}
