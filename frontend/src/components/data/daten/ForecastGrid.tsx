import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import WeatherGlyph from "./WeatherGlyph";

const WEEKDAY = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" });

/**
 * 8-day outlook grid (Figma Frame 67, right of the middle band): weekday +
 * date, a condition glyph, and the day's high/low. Every glyph is rendered at
 * one fixed size so the grid reads as a uniform matrix (the caller's
 * uniformity requirement).
 */
export default function ForecastGrid({ forecast }: { forecast: NormalizedForecastSeries }) {
  const days = forecast.days.slice(0, 8);
  if (!days.length) return null;

  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-8 sm:grid-cols-4">
      {days.map((day) => {
        const date = day.local_date ?? day.date;
        const d = new Date(`${date}T12:00:00Z`);
        const weekday = WEEKDAY.format(d).replace(".", "").toUpperCase();
        const label = `${weekday} ${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
        const hi = day.summary.air_max ?? day.summary.temperature_max_c;
        const lo = day.summary.air_min ?? day.summary.temperature_min_c;
        return (
          <div key={date} className="flex flex-col items-start gap-3">
            <p className="text-ui tabular-nums text-ink">{label}</p>
            <WeatherGlyph condition={day.summary.weather_condition} size={44} />
            <p className="text-ui tabular-nums">
              <span className="text-ink">{hi == null ? "–" : Math.round(hi)}C</span>{" "}
              <span className="text-[#4F97D8]">{lo == null ? "–" : Math.round(lo)}C</span>
            </p>
          </div>
        );
      })}
    </div>
  );
}
