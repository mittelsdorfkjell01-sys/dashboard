import { useMemo } from "react";
import type { NormalizedForecastHour, NormalizedForecastSeries } from "../../lib/forecastNormalization";
import { windColor } from "../../lib/windScale";
import { formatWind, useSpotDataScope } from "../../state/SpotDataScope";
import WindArrow from "../WindArrow";
import WindScaleLegend from "../WindScaleLegend";
import { buildMeteogramModel } from "./meteogramModel";

// Week-overview design from the pre-Meteogram `Forecast.tsx` (removed in
// d8e99980) — one button per day, a handful of colored wind bars (height and
// hue both encode wind speed via the shared `windColor()` scale) plus a
// direction arrow and the day's peak wind. Much simpler and more colorful
// than the axis-table chart, and a better fit for the map's small panel than
// the full Meteogram (which stays on the Daten tab).
type DayBlock = { date: string; hours: { label: string; wind: number | null; dir: number | null }[]; maxWind: number | null; dir: number | null };

function dayBlocks(hours: NormalizedForecastHour[]): { label: string; wind: number | null; dir: number | null }[] {
  return hours.filter((hour) => hour.localHour % 3 === 0).map((hour) => ({ label: hour.localTime.slice(0, 2), wind: hour.wind, dir: hour.dir }));
}

function dayLabel(date: string): string { return new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`)).replace(".", "").toUpperCase(); }
function dayDate(date: string): string { return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`)); }

export default function MapForecastChart({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedAtUtc, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const model = useMemo(() => buildMeteogramModel(forecast), [forecast]);
  const days = useMemo<DayBlock[]>(() => model.detailDays.map((day) => {
    const blocks = dayBlocks(day.hours);
    const winds = blocks.map((b) => b.wind).filter((v): v is number => v != null);
    const midday = day.hours.find((hour) => hour.localHour >= 11 && hour.localHour <= 13) ?? day.hours[Math.floor(day.hours.length / 2)];
    return { date: day.local_date ?? day.date, hours: blocks, maxWind: winds.length ? Math.max(...winds) : null, dir: midday?.dir ?? null };
  }), [model.detailDays]);
  const weekMaxKts = Math.max(1, ...days.flatMap((day) => day.hours.map((b) => b.wind ?? 0)));

  if (!days.length) return <div className="border-y border-line bg-band/40 px-4 py-5 text-ui text-muted">Für diesen Zeitraum sind keine Prognosedaten verfügbar.</div>;

  const selectDay = (day: DayBlock) => {
    const midday = model.slots.find((slot) => slot.localDate === day.date && slot.localHour >= 11 && slot.localHour <= 13) ?? model.slots.find((slot) => slot.localDate === day.date);
    if (midday) setSelectedAtUtc(midday.utcKey);
  };

  return (
    <div className="border-y border-line bg-surface px-1 py-2">
      <div className="min-w-0 max-w-full overflow-x-auto no-scrollbar">
        <div className="grid grid-flow-col auto-cols-[minmax(84px,1fr)] divide-x divide-line">
          {days.map((day) => {
            const selected = model.slots.some((slot) => slot.localDate === day.date && slot.utcKey === selectedAtUtc);
            return (
              <button key={day.date} type="button" onClick={() => selectDay(day)} aria-pressed={selected} aria-label={`${dayLabel(day.date)} ${dayDate(day.date)} auswählen`} className={`flex snap-start flex-col items-center gap-2 px-2 py-2 text-center ${selected ? "bg-band" : ""}`}>
                <div>
                  <div className="text-caption font-semibold text-ink">{dayLabel(day.date)}</div>
                  <div className="text-caption text-muted">{dayDate(day.date)}</div>
                </div>
                <div aria-hidden="true" className="flex h-16 items-end gap-0.5">
                  {day.hours.map((b, j) => {
                    const pct = b.wind == null ? 4 : Math.max(6, (b.wind / weekMaxKts) * 100);
                    return (
                      <div key={j} className="flex h-full w-2.5 flex-col justify-end" title={`${b.label} Uhr`}>
                        <div className="w-full rounded-t-[2px]" style={{ height: `${pct}%`, backgroundColor: windColor(b.wind) }} />
                      </div>
                    );
                  })}
                </div>
                <div className="flex flex-col items-center gap-1 border-t border-line pt-1.5">
                  {day.dir != null ? <WindArrow dir={day.dir} size={14} className="text-ink-soft" /> : <span className="text-line" aria-hidden="true">—</span>}
                  <span className="text-label font-semibold tabular-nums text-ink">{day.maxWind != null ? formatWind(day.maxWind, windUnit) : "—"}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
      <div className="mt-2 px-2"><WindScaleLegend /></div>
    </div>
  );
}
