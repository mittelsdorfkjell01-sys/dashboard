import { useMemo } from "react";
import { sunTimes } from "../../lib/sunTimes";

// Same longitude-as-timezone approximation as sunTimes()/isDaytime() — this
// is a chart accent, not a legal/scientific time (see lib/sunTimes.ts).
function localDecimalHour(lng: number, now: Date): number {
  const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600;
  return ((utcHour + lng / 15) % 24 + 24) % 24;
}

function formatHour(decimalHour: number): string {
  let h = Math.floor(decimalHour);
  let m = Math.round((decimalHour - h) * 60);
  if (m === 60) { m = 0; h += 1; }
  return `${String(((h % 24) + 24) % 24).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Sunrise/sunset arc for the spot's coordinates — a Daten-tab companion to
 *  TidePanel's tide curve, not merged into one widget: a day has one
 *  sunrise/sunset, so an arc fits; a tide cycle has two highs and two lows,
 *  which an arc would misrepresent (see the wireframe review). */
export default function SunArc({ lat, lng }: { lat: number; lng: number }) {
  const now = new Date();
  const sun = useMemo(() => sunTimes(lat, lng, now), [lat, lng, now.toDateString()]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sun) {
    return (
      <div>
        <p className="text-caption font-medium uppercase tracking-wider text-muted">Licht</p>
        <p className="mt-2 text-label text-muted">Für diesen Breitengrad lässt sich kein Sonnenauf-/-untergang berechnen.</p>
      </div>
    );
  }

  const { sunrise, sunset } = sun;
  const dayLength = sunset - sunrise;
  const localHour = localDecimalHour(lng, now);
  const isDay = localHour >= sunrise && localHour < sunset;
  const progress = Math.min(1, Math.max(0, (localHour - sunrise) / dayLength));

  const cx = 130, cy = 108, r = 104;
  const angle = Math.PI * (1 - progress); // π at sunrise (left) → 0 at sunset (right)
  const sunX = cx + r * Math.cos(angle);
  const sunY = cy - r * Math.sin(angle);
  const hoursLabel = `${Math.floor(dayLength)} Std. ${Math.round((dayLength % 1) * 60)} Min.`;

  return (
    <div>
      <p className="text-caption font-medium uppercase tracking-wider text-muted">Licht</p>
      <p className="mt-1 text-ui font-semibold text-ink">
        {isDay ? "Tageslicht" : "Nach Sonnenuntergang"} <span className="font-normal text-muted">· {hoursLabel} Tageslicht heute</span>
      </p>
      <svg
        viewBox="0 0 260 130"
        className="mt-3 h-auto w-full max-w-xs"
        role="img"
        aria-label={`Sonnenaufgang ${formatHour(sunrise)} Uhr, Sonnenuntergang ${formatHour(sunset)} Uhr, aktuell ${isDay ? "Tageslicht" : "Dunkelheit"}.`}
      >
        <path d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`} fill="none" stroke="var(--sw-line)" strokeWidth={2} strokeDasharray="1 7" strokeLinecap="round" />
        <path d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${sunX},${sunY}`} fill="none" stroke="var(--sw-orange)" strokeWidth={2.5} strokeLinecap="round" />
        <circle cx={sunX} cy={sunY} r={6.5} fill="var(--sw-surface)" stroke="var(--sw-orange)" strokeWidth={3} />
        <circle cx={cx - r} cy={cy} r={3} fill="var(--sw-muted)" />
        <circle cx={cx + r} cy={cy} r={3} fill="var(--sw-muted)" />
      </svg>
      <div className="mt-1 flex max-w-xs justify-between">
        <div>
          <p className="text-caption uppercase tracking-wider text-muted">Aufgang</p>
          <p className="text-label font-semibold tabular-nums text-ink">{formatHour(sunrise)}</p>
        </div>
        <div className="text-right">
          <p className="text-caption uppercase tracking-wider text-muted">Untergang</p>
          <p className="text-label font-semibold tabular-nums text-ink">{formatHour(sunset)}</p>
        </div>
      </div>
      <p className="mt-2 max-w-xs text-caption text-muted">Näherungswert (±wenige Minuten), berechnet aus Position und Datum.</p>
    </div>
  );
}
