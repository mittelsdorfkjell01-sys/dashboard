import type { NormalizedForecastDay } from "../../lib/forecastNormalization";
import { windColor } from "../../lib/windScale";
import { formatWind, type WindUnit } from "../../state/SpotDataScope";

const dayLabel = (date: string) => new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
const value = (number: number | null | undefined, unit: string, digits = 0) => number == null ? "—" : `${number.toFixed(digits)} ${unit}`;

export default function MeteogramTrend({ days, windUnit }: { days: NormalizedForecastDay[]; windUnit: WindUnit }) {
  if (!days.length) return null;
  return <section className="border-t border-line bg-band/40 px-4 py-4" aria-labelledby="meteogram-trend-title">
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <h3 id="meteogram-trend-title" className="text-ui font-semibold text-ink">Tagestrend · Tage 6–10</h3>
      <p className="text-caption text-muted">Tageswerte ohne scheinbare Stundenauflösung</p>
    </div>
    <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal" tabIndex={0} role="region" aria-label="Tagestrend horizontal scrollen">
      <div className="grid min-w-[620px] grid-flow-col auto-cols-fr divide-x divide-line">
        {days.map((day) => { const summary=day.summary; return <div key={day.date} className="px-3 py-2 first:pl-0 last:pr-0">
          <p className="text-label font-semibold text-ink">{dayLabel(day.local_date ?? day.date)}</p>
          <p className="mt-0.5 text-caption text-muted">Sicherheit {day.confidence ?? "nicht verfügbar"}</p>
          <dl className="mt-3 space-y-1.5 text-caption tabular-nums">
            <div className="flex justify-between gap-3"><dt className="text-muted">Wind Ø / max.</dt><dd className="font-medium text-ink"><span className="mr-1 inline-block h-2.5 w-2.5 rounded-[2px]" style={{backgroundColor:windColor(summary.wind_avg)}} />{windValue(summary.wind_avg,windUnit)} / {windValue(summary.wind_max,windUnit)}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-muted">Böe</dt><dd className="font-medium text-ink">{windValue(summary.gust_max,windUnit)}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-muted">Temperatur</dt><dd className="font-medium text-ink">{value(summary.air_min,"°C")}–{value(summary.air_max,"°C")}</dd></div>
            {summary.swell_max != null&&<div className="flex justify-between gap-3"><dt className="text-muted">Wellenhöhe</dt><dd className="font-medium text-ink">{value(summary.swell_max,"m",1)}</dd></div>}
          </dl>
        </div>; })}
      </div>
    </div>
  </section>;
}

const windValue = (number: number | null | undefined, unit: WindUnit) => number == null ? "—" : `${formatWind(number,unit)} ${unit === "ms" ? "m/s" : "kt"}`;
