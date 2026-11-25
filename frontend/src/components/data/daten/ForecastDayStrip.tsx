import { useMemo } from "react";
import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { isSpotForecastDisplayHour, spotForecastDayHours } from "../../../lib/spotForecastWindow";
import { windColor } from "../../../lib/windScale";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import { formatWave, formatWind } from "../../../lib/units";
import { useOptionalUnits } from "../../../context/PrefsContext";
import { headlineWaveM } from "../../../lib/waveReading";
import type { DatenFocus } from "./datenFocus";
import { scrollMeteogramToDay } from "./scrollMeteogramToDay";

const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" });

// One bar per local hour of the spot window, 06 to 20 — fifteen per day.
const BAR_HOURS = Array.from({ length: 15 }, (_, i) => 6 + i);
const BAND_H = 42; // bar band height (px) — a third lower since 2026-11-25
const MAX_DAYS = 10;

/**
 * Ten-day overview above the meteogram (chosen 2026-11-24, "Durchgehendes
 * Windband"): every hour of the spot window for all ten days as one bar
 * band, the days as columns above it with weekday and date. Read across, it
 * shows how the wind builds and drops over several days, not just inside
 * one. Bars use the site's wind colours on the band's own scale.
 * A tap on a day scrolls the meteogram to it and selects its first hour; the
 * selected day is tinted.
 */
export default function ForecastDayStrip({ forecast, focus = "wind" }: { forecast: NormalizedForecastSeries; focus?: DatenFocus }) {
  const { selectedForecast, setSelectedAtUtc, windUnit } = useSpotDataScope();
  const units = useOptionalUnits();
  const waveFocus = focus === "wave";
  const days = useMemo(() => forecast.days.slice(0, MAX_DAYS), [forecast]);
  // Wave focus (2026-11-25): the same band shows the total wave per hour.
  const dayBars = useMemo(
    () => days.map((day) => hourlyBars(day.hours, waveFocus ? headlineWaveM : (hour) => hour.wind)),
    [days, waveFocus],
  );
  if (!days.length) return null;

  // The band scales to its own strongest hour (at least 10 kn), so a calm
  // week still fills the height and the ten days stay comparable to each
  // other. (Sharing the meteogram's gust-inclusive scale left the bars flat.)
  const windMax = Math.max(waveFocus ? 1 : 10, ...dayBars.flat().filter((wind): wind is number => wind != null));

  const selectDay = (day: NormalizedForecastDay) => {
    const firstHour = spotForecastDayHours(day)[0];
    if (!firstHour) return;
    setSelectedAtUtc(firstHour.utcKey);
    scrollMeteogramToDay(day.local_date ?? day.date);
  };

  const selectedIndex = days.findIndex((day) => (day.local_date ?? day.date) === selectedForecast?.localDate);

  return (
    <div
      className="relative grid grid-cols-10"
      role="group"
      aria-label="Tagesübersicht — Tag im Stundenforecast anzeigen"
    >
      {/* One tint for the chosen day that glides to the next choice (200 ms,
          chosen 2026-11-25, "Markierung gleitet") instead of jumping. */}
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-0 left-0 w-[10%] bg-teal/15 transition-[transform,opacity] duration-base ease-brand motion-reduce:transition-none ${
          selectedIndex < 0 ? "opacity-0" : "opacity-100"
        }`}
        style={{ transform: `translateX(${Math.max(0, selectedIndex) * 100}%)` }}
      />
      {days.map((day, index) => {
        const date = day.local_date ?? day.date;
        const d = new Date(`${date}T12:00:00Z`);
        const weekday = WEEKDAY.format(d).replace(".", "");
        const dayMonth = `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.`;
        const dayOfMonth = `${String(d.getUTCDate()).padStart(2, "0")}.`;
        const bars = dayBars[index];
        const peak = bars.reduce<number | null>((max, w) => (w == null ? max : max == null ? w : Math.max(max, w)), null);
        const selected = selectedForecast?.localDate === date;

        return (
          <button
            key={date}
            type="button"
            aria-pressed={selected}
            aria-label={`${weekday} ${dayMonth}${peak == null ? "" : `, bis ${waveFocus ? formatWave(peak, units.wave) : formatWind(peak, windUnit)}`} — im Stundenforecast anzeigen`}
            title="Im Stundenforecast anzeigen"
            onClick={() => selectDay(day)}
            className="relative flex min-w-0 flex-col border-l border-line pb-1 pl-1 pr-px text-left transition-colors duration-fast first:border-l-0 hover:bg-line-soft focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-teal motion-reduce:transition-none sm:pl-1.5"
          >
            <span className="block text-caption font-semibold leading-tight text-ink sm:text-ui">{weekday}</span>
            <span className="block text-micro leading-tight tabular-nums text-muted sm:text-caption">
              <span className="sm:hidden">{dayOfMonth}</span>
              <span className="hidden sm:inline">{dayMonth}</span>
            </span>
            <span className="mt-1.5 grid items-end" style={{ height: BAND_H, gridTemplateColumns: `repeat(${BAR_HOURS.length}, minmax(0, 1fr))` }} aria-hidden="true">
              {bars.map((wind, i) => (
                <span
                  key={i}
                  data-wind-bar
                  className="mx-[0.5px] rounded-t-[1px]"
                  style={{
                    height: wind == null ? 2 : Math.max(3, (wind / windMax) * BAND_H),
                    background: wind == null ? "var(--sw-line)" : waveFocus ? "var(--sw-data-swell)" : windColor(wind),
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

/**
 * Loading placeholder in the band's final size: the same ten columns, the
 * same two text lines and the same bar height, so the band replaces it
 * without moving the meteogram below.
 */
export function ForecastDayStripSkeleton() {
  return (
    <div className="grid grid-cols-10" aria-hidden="true">
      {Array.from({ length: MAX_DAYS }).map((_, index) => (
        <div key={index} className="flex min-w-0 flex-col border-l border-line pb-1 pl-1 pr-px first:border-l-0 sm:pl-1.5">
          <span className="block text-caption font-semibold leading-tight text-transparent sm:text-ui">Mo</span>
          <span className="block text-micro leading-tight text-transparent sm:text-caption">01.</span>
          <span className="mt-1.5 flex animate-pulse items-end gap-px motion-reduce:animate-none" style={{ height: BAND_H }}>
            {BAR_HOURS.map((hour) => (
              <span key={hour} className="flex-1 rounded-t-[1px] bg-line" style={{ height: 10 + ((hour * 7 + index * 3) % 9) * 3 }} />
            ))}
          </span>
        </div>
      ))}
    </div>
  );
}

// One value per local hour 06–20. Forecasts thin out to 3- or 6-hourly steps
// after the first days; each slot then carries the latest earlier reading of
// the same day (or the first later one before the day's first reading), so a
// coarse day still reads as a continuous band instead of a comb. A day with no
// hourly data at all (trend-only) renders as faint stubs.
function hourlyBars(hours: NormalizedForecastHour[], read: (hour: NormalizedForecastHour) => number | null | undefined): (number | null)[] {
  const known = hours
    .filter((hour) => isSpotForecastDisplayHour(hour) && read(hour) != null)
    .map((hour) => ({ h: hour.localHour, wind: read(hour) as number }))
    .sort((a, b) => a.h - b.h);
  if (!known.length) return BAR_HOURS.map(() => null);
  return BAR_HOURS.map((slot) => {
    let pick = known[0];
    for (const reading of known) {
      if (reading.h <= slot) pick = reading;
      else break;
    }
    return pick.wind;
  });
}
