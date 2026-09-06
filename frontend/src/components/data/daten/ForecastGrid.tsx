import type { NormalizedForecastDay, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { spotForecastDayHours } from "../../../lib/spotForecastWindow";
import { useSpotDataScope } from "../../../state/SpotDataScope";
import { scrollMeteogramToDay } from "./scrollMeteogramToDay";
import WeatherGlyph, { weatherLabel } from "./WeatherGlyph";
import { tempColor, COLDEST_TEMP_COLOR } from "../../../lib/tempScale";

const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" });

/**
 * Compact 10-day outlook. Days with hourly data act as navigation into the
 * meteogram; trend-only days keep the original read-only presentation.
 */
export default function ForecastGrid({ forecast }: { forecast: NormalizedForecastSeries }) {
  const { selectedForecast, setSelectedAtUtc } = useSpotDataScope();
  const days = forecast.days.slice(0, 10);
  if (!days.length) return null;

  const selectDay = (day: NormalizedForecastDay) => {
    const firstHour = spotForecastDayHours(day)[0];
    if (!firstHour) return;

    setSelectedAtUtc(firstHour.utcKey);
    scrollMeteogramToDay(day.local_date ?? day.date);
  };

  return (
    <div className="forecast-weather-grid grid w-full grid-cols-5 gap-x-1.5 gap-y-5 sm:gap-x-3 sm:gap-y-7 lg:gap-x-2 xl:gap-x-4">
      {days.map((day) => {
        const date = day.local_date ?? day.date;
        const d = new Date(`${date}T12:00:00Z`);
        const weekday = WEEKDAY.format(d).replace(".", "").toUpperCase();
        const label = `${weekday} ${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
        const hi = day.summary.air_max ?? day.summary.temperature_max_c;
        const lo = day.summary.air_min ?? day.summary.temperature_min_c;
        const condition = weatherLabel(day.summary.weather_condition);
        const selectable = spotForecastDayHours(day).length > 0;
        const selected = selectable && selectedForecast?.localDate === date;

        return (
          <div key={date} className="flex min-w-0 flex-col items-center">
            <button
              type="button"
              disabled={!selectable}
              aria-pressed={selectable ? selected : undefined}
              aria-label={selectable ? `${label}: ${condition}. Im Stundenforecast anzeigen.` : undefined}
              title={selectable ? "Im Stundenforecast anzeigen" : "Noch keine Stundenwerte verfügbar"}
              onClick={() => selectDay(day)}
              className="flex min-h-11 w-full min-w-0 flex-col items-center gap-2 text-center transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-default disabled:opacity-100"
            >
              <span className={`whitespace-nowrap text-sz-11 leading-none tabular-nums sm:text-caption xl:text-label ${selected ? "text-teal" : "text-ink"}`}>{label}</span>
              <span aria-hidden="true">
                <WeatherGlyph condition={day.summary.weather_condition} size={40} className="h-7 w-7 sm:h-9 sm:w-9 lg:h-8 lg:w-8 xl:h-10 xl:w-10" />
              </span>
              <span className="sr-only text-caption leading-tight text-muted sm:not-sr-only sm:min-h-8 lg:sr-only xl:not-sr-only xl:min-h-8">{condition}</span>
              {/* High tinted by its value on the absolute temp→colour scale (same
                  value ⇒ same colour across days), primary weight/colour. Low is
                  held back (normal weight, reduced opacity) and always the coolest
                  tone, so a low never reads as warm even on a hot day. The °
                  inherits its number's colour. */}
              <span className="whitespace-nowrap text-sz-11 leading-tight tabular-nums sm:text-caption xl:text-label">
                {hi == null ? (
                  <span className="text-muted">—</span>
                ) : (
                  <span className="font-semibold" style={{ color: tempColor(hi) }}>{Math.round(hi)}°</span>
                )}{" "}
                {lo == null ? (
                  <span className="text-muted">—</span>
                ) : (
                  <span className="font-normal" style={{ color: COLDEST_TEMP_COLOR, opacity: 0.78 }}>{Math.round(lo)}°</span>
                )}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
