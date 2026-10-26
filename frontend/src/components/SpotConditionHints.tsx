import type { ForecastSummaryRead } from "../lib/api";
import type { Spot } from "../lib/types";
import { GroundIcon, SafetyIcon, TemperatureIcon, WindIcon } from "../lib/icons";
import { buildSpotConditionHints } from "../lib/spotConditionHints";

export default function SpotConditionHints({ spot, forecast }: { spot: Spot; forecast?: ForecastSummaryRead | null }) {
  const hints = buildSpotConditionHints(spot, forecast);
  if (!hints.length) return null;
  return (
    <section aria-labelledby="spot-condition-hints-title" aria-live="polite" className="mt-8 border-y border-line py-5 sm:mt-10 sm:py-6">
      <h2 id="spot-condition-hints-title" className="text-ui font-semibold text-ink">
        Sicherheits- und Lagehinweise
      </h2>
      <ul className="mt-4 divide-y divide-line">
        {hints.map((hint) => {
          const Icon = hint.kind === "safety"
            ? SafetyIcon
            : hint.kind === "wind"
              ? WindIcon
              : hint.kind === "temperature"
                ? TemperatureIcon
                : GroundIcon;
          return (
            <li key={hint.id} className="flex min-w-0 gap-3 py-3 first:pt-0 last:pb-0">
              <Icon aria-hidden width={20} height={20} className="mt-0.5 shrink-0 text-teal" />
              <div className="min-w-0">
                <p className="text-ui leading-relaxed text-ink">{hint.sentence}</p>
                <p className="mt-1 text-caption leading-relaxed text-muted">
                  <span className="font-medium text-ink-soft">{hint.sourceLabel}</span>
                  {hint.timing ? ` · ${hint.timing}` : ""}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
