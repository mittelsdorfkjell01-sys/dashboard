import type { NormalizedForecastDay, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import WeatherGlyph, { weatherLabel } from "./WeatherGlyph";

const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" });

/**
 * Compact 8-day outlook. Days with hourly data act as navigation into the
 * meteogram; trend-only days keep the original read-only presentation.
 */
export default function ForecastGrid({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedForecast, setSelectedAtUtc } = useSpotDataScope();
  const days = forecast.days.slice(0, 8);
  if (!days.length) return null;

  const selectDay = (day: NormalizedForecastDay) => {
    const firstHour = day.hours[0];
    if (!firstHour) return;

    setSelectedAtUtc(firstHour.utcKey);
    const date = day.local_date ?? day.date;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = reducedMotion ? "auto" : "smooth";

    requestAnimationFrame(() => {
      const scroller = document.getElementById("spot-meteogram-scroll");
      const dayAnchor = Array.from(scroller?.querySelectorAll<HTMLElement>("[data-forecast-day]") ?? [])
        .find((element) => element.dataset.forecastDay === date);
      if (scroller && dayAnchor) {
        scroller.scrollTo({ left: dayAnchor.offsetLeft, top: 0, behavior });
      }
      document.getElementById("spot-meteogramm")?.scrollIntoView({ behavior, block: "start" });
    });
  };

  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-8 sm:grid-cols-4">
      {days.map((day) => {
        const date = day.local_date ?? day.date;
        const d = new Date(`${date}T12:00:00Z`);
        const weekday = WEEKDAY.format(d).replace(".", "").toUpperCase();
        const label = `${weekday} ${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
        const hi = day.summary.air_max ?? day.summary.temperature_max_c;
        const lo = day.summary.air_min ?? day.summary.temperature_min_c;
        const condition = weatherLabel(day.summary.weather_condition);
        const selectable = day.hours.length > 0;
        const selected = selectable && selectedForecast?.localDate === date;

        return (
          <div key={date} className="flex flex-col items-start gap-3">
            <button
              type="button"
              disabled={!selectable}
              aria-pressed={selectable ? selected : undefined}
              aria-label={selectable ? `${label}: ${condition}. Im Stundenforecast anzeigen.` : undefined}
              title={selectable ? "Im Stundenforecast anzeigen" : "Noch keine Stundenwerte verfügbar"}
              onClick={() => selectDay(day)}
              className="flex min-h-11 w-full flex-col items-start gap-3 text-left transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal disabled:cursor-default disabled:opacity-100"
            >
              <span className={`text-ui tabular-nums ${selected ? "text-teal" : "text-ink"}`}>{label}</span>
              <span aria-hidden="true">
                <WeatherGlyph condition={day.summary.weather_condition} size={44} />
              </span>
              <span className="text-label leading-tight text-muted">{condition}</span>
              <span className="text-ui tabular-nums">
                <span className="text-ink">{hi == null ? "—" : Math.round(hi)}C</span>{" "}
                <span className="text-muted">{lo == null ? "—" : Math.round(lo)}C</span>
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
