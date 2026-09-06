import { useMemo } from "react";
import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { isSpotForecastDisplayHour, spotForecastDayHours } from "../../../lib/spotForecastWindow";
import { windColor } from "../../../lib/windScale";
import { buildMeteogramModel } from "../meteogramModel";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import { scrollMeteogramToDay } from "./scrollMeteogramToDay";

const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" });

// Tile + bar geometry from Figma node 510-5 (Frame 72). Each day is a FILLED
// rounded rectangle (no stroke) holding exactly 8 wind bars. All ten days stay
// visible: two rows of five on compact screens and one row of ten on desktop.
// Bars flex to fill each tile; only their count, gaps and height are fixed.
const BAR_HOURS = [6, 8, 10, 12, 14, 16, 18, 20]; // 8 fixed local-hour slots (06..20)
const BAR_GAP = 3; // gap between bars (px)
const BAR_BAND_H = 30; // bar-band / max bar height (px)
const TILE_H = 57;
const TILE_GAP = 6; // gap between day tiles (px)
const MAX_DAYS = 10;

/**
 * Compact multi-day navigator sitting above the meteogram (Figma node 510-5).
 * All forecast days (up to ten) are shown as small filled tiles spanning the
 * body width, each with a weekday (left) + date (right) caption and a fixed
 * eight-bar wind profile, so days compare directly at a glance. For a day
 * already in progress the elapsed hours are drawn as normal bars (not dropped),
 * so today reads the same as any other day. Clicking a day scrolls the
 * meteogram to it and selects its first hour, like Windfinder's day tabs. Bar
 * heights share the meteogram's wind scale (expanded only if a far-out day
 * exceeds it, so nothing overflows); colours come from the shared wind scale.
 */
export default function ForecastDayStrip({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedForecast, setSelectedAtUtc } = useSpotDataScope();
  const model = useMemo(() => buildMeteogramModel(forecast, isSpotForecastDisplayHour), [forecast]);
  const days = useMemo(() => forecast.days.slice(0, MAX_DAYS), [forecast]);
  const dayBars = useMemo(() => days.map((day) => miniBars(day.hours)), [days]);
  if (!days.length) return null;

  // Shared meteogram scale, widened only if a day's bar exceeds it so bars never
  // overflow the band. Stays identical to the meteogram when nothing exceeds it.
  const windMax = Math.max(
    model.scales.wind.max,
    1,
    ...dayBars.flat().filter((wind): wind is number => wind != null),
  );

  const selectDay = (day: NormalizedForecastDay) => {
    const firstHour = spotForecastDayHours(day)[0];
    if (!firstHour) return;
    setSelectedAtUtc(firstHour.utcKey);
    scrollMeteogramToDay(day.local_date ?? day.date);
  };

  return (
    <div
      className="grid grid-cols-5 pb-1 lg:grid-cols-10"
      style={{ gap: TILE_GAP }}
      role="group"
      aria-label="Tagesübersicht — Tag im Stundenforecast anzeigen"
    >
      {days.map((day, index) => {
        const date = day.local_date ?? day.date;
        const d = new Date(`${date}T12:00:00Z`);
        const weekday = WEEKDAY.format(d).replace(".", "").toUpperCase();
        const dayMonth = `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.`;
        const bars = dayBars[index];
        const selected = selectedForecast?.localDate === date;

        return (
          <button
            key={date}
            type="button"
            aria-pressed={selected}
            aria-label={`${weekday} ${dayMonth} — im Stundenforecast anzeigen`}
            title="Im Stundenforecast anzeigen"
            onClick={() => selectDay(day)}
            style={{ height: TILE_H }}
            className="flex min-w-0 flex-col justify-between rounded-[10px] bg-[#0E141B] px-[5px] pb-1 pt-[3px] transition-colors hover:bg-line-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
          >
            <span className="flex items-baseline justify-between gap-1 whitespace-nowrap text-sz-10 leading-none tabular-nums max-[359px]:flex-col max-[359px]:items-start max-[359px]:gap-0 sm:text-sz-11 xl:text-label">
              <span className="font-medium text-ink">{weekday}</span>
              <span className="text-muted">{dayMonth}</span>
            </span>
            <span className="flex items-end" style={{ height: BAR_BAND_H, gap: BAR_GAP }} aria-hidden="true">
              {bars.map((wind, i) => (
                <span
                  key={i}
                  className="min-w-0 flex-1 rounded-[3px]"
                  style={{
                    height: wind == null ? 3 : Math.max(3, (wind / windMax) * BAR_BAND_H),
                    background: wind == null ? "var(--sw-line)" : windColor(wind),
                  }}
                />
              ))}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// Exactly eight bars per day — one per fixed local-hour slot (06, 08, … 20)
// inside the spot display window — so every day shows the same 8-bar profile.
// A day already in progress keeps its elapsed hours (they are real forecast
// slots, not dropped), and any slot without data renders as a faint stub rather
// than shrinking the tile, keeping all bars horizontally aligned across days.
function miniBars(hours: NormalizedForecastHour[]): (number | null)[] {
  const byHour = new Map<number, number>();
  for (const hour of hours) {
    if (!isSpotForecastDisplayHour(hour) || hour.wind == null) continue;
    if (!byHour.has(hour.localHour)) byHour.set(hour.localHour, hour.wind);
  }
  return BAR_HOURS.map((hr) => (byHour.has(hr) ? byHour.get(hr)! : null));
}
