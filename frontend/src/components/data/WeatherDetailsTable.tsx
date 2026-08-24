import type { ForecastSeries, WeatherCondition } from "../../lib/api";
import type { NormalizedForecastSeries } from "../../lib/forecastNormalization";

const labels: Record<WeatherCondition, string> = {
  clear: "Klar", mainly_clear: "Überwiegend klar", partly_cloudy: "Teilweise bewölkt",
  overcast: "Bedeckt", fog: "Nebel", drizzle: "Nieselregen", rain: "Regen",
  snow: "Schnee", rain_showers: "Regenschauer", snow_showers: "Schneeschauer",
  thunderstorm: "Gewitter", unknown: "Nicht verfügbar",
};
const value = (n: number | null | undefined, unit = "", digits = 0) => n == null ? "Nicht verfügbar" : `${n.toFixed(digits)}${unit}`;
const clock = (instant: string | null | undefined, timezone = "UTC") => instant ? new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: timezone }).format(new Date(instant)) : null;
const solar = (summary: ForecastSeries["days"][number]["summary"], timezone: string) => {
  if (summary.solar_state === "polar_day") return "Polartag";
  if (summary.solar_state === "polar_night") return "Polarnacht";
  const rise = clock(summary.sunrise_at, timezone), set = clock(summary.sunset_at, timezone);
  return rise && set ? `${rise}–${set}` : "Nicht verfügbar";
};

function WeatherIcon({ condition = "unknown", isDay, label }: { condition?: WeatherCondition; isDay?: boolean | null; label: string }) {
  const storm = condition === "thunderstorm";
  const wet = ["drizzle", "rain", "rain_showers", "snow", "snow_showers"].includes(condition);
  return <svg role="img" aria-label={`${label}${isDay == null ? "" : isDay ? ", Tag" : ", Nacht"}`} viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-teal" fill="none" stroke="currentColor" strokeWidth="1.7">
    {condition === "clear" || condition === "mainly_clear" ? <><circle cx="12" cy="12" r={isDay === false ? "5" : "4"}/>{isDay !== false && <path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9 7 7m10 10 2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>}</> : <><path d="M6 17h11a4 4 0 0 0 0-8 6 6 0 0 0-11.3 1.8A3.2 3.2 0 0 0 6 17Z"/>{wet && <path d="m8 19-1 2m5-2-1 2m5-2-1 2"/>}{storm && <path d="m13 17-2 3h2l-2 3"/>}</>}
  </svg>;
}

export default function WeatherDetailsTable({ forecast }: { forecast: NormalizedForecastSeries }) {
  if (!forecast.days.length) return null;
  const timezone = forecast.timezone ?? "UTC";
  const hours = forecast.days.flatMap((day) => day.hours).slice(0, 24);
  return <div className="space-y-6 px-2 pb-3">
    <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal" tabIndex={0} role="region" aria-label="Tägliche Wettervorhersage horizontal scrollen">
      <table aria-label="Tägliche Wettervorhersage" className="min-w-[820px] w-full border-collapse text-ui tabular-nums">
        <thead><tr>{["Tag", "Wetter", "Temperatur", "Regen", "Wolken", "UV max.", "Sonne"].map((label) => <th scope="col" key={label} className="border-b border-line px-2.5 py-2 text-left text-caption font-medium uppercase tracking-wide text-muted [&:not(:first-child)]:text-right">{label}</th>)}</tr></thead>
        <tbody>{forecast.days.map((day, index) => { const s = day.summary; const condition = s.weather_condition ?? "unknown"; return <tr key={day.date} className={index === 0 ? "bg-band" : ""}>
          <th scope="row" className="border-b border-line-soft px-2.5 py-2 text-left font-medium text-ink">{formatDay(day.local_date ?? day.date)} <span className="font-normal text-muted">{formatDate(day.local_date ?? day.date)}</span></th>
          <td className="border-b border-line-soft px-2.5 py-2"><span className="flex items-center justify-end gap-2"><WeatherIcon condition={condition} label={labels[condition]} />{labels[condition]}</span></td>
          <td className="border-b border-line-soft px-2.5 py-2 text-right" title="Maximum / Minimum">{value(s.temperature_max_c ?? s.air_max, " °C")} / {value(s.temperature_min_c ?? s.air_min, " °C")}</td>
          <td className="border-b border-line-soft px-2.5 py-2 text-right">{value(s.precipitation_sum_mm, " mm", 1)}</td>
          <td className="border-b border-line-soft px-2.5 py-2 text-right">{value(s.cloud_cover_mean_pct, " %")}</td>
          <td className="border-b border-line-soft px-2.5 py-2 text-right">{value(s.uv_index_max, "", 1)}</td>
          <td className="border-b border-line-soft px-2.5 py-2 text-right">{solar(s, timezone)}</td>
        </tr>; })}</tbody>
      </table>
    </div>
    {hours.length > 0 && <div className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal" tabIndex={0} role="region" aria-label="Stündliche Wettervorhersage horizontal scrollen"><table aria-label="Stündliche Wettervorhersage" className="min-w-[980px] w-full border-collapse text-ui tabular-nums">
      <caption className="px-2.5 pb-2 text-left font-semibold text-ink">Nächste 24 Stunden</caption>
      <thead><tr>{["Zeit", "Wetter", "Temperatur", "Gefühlt", "Regen", "Wolken", "Druck", "UV", ...(forecast.availability?.marine === "available" ? ["Welle", "Meeresoberfläche"] : [])].map((label) => <th scope="col" key={label} className="border-b border-line px-2.5 py-2 text-left text-caption font-medium uppercase tracking-wide text-muted [&:not(:first-child)]:text-right">{label}</th>)}</tr></thead>
      <tbody>{hours.map((hour) => { const condition = hour.weather_condition ?? "unknown"; return <tr key={hour.utcKey}>
        <th scope="row" className="border-b border-line-soft px-2.5 py-2 text-left font-medium">{formatDay(hour.localDate)} {hour.localTimeWithOffset}</th>
        <td className="border-b border-line-soft px-2.5 py-2"><span className="flex items-center justify-end gap-2"><WeatherIcon condition={condition} isDay={hour.is_day} label={labels[condition]} />{labels[condition]}</span></td>
        {[value(hour.air, " °C", 1), value(hour.apparent_temperature_c, " °C", 1), value(hour.precip, " mm", 1), value(hour.cloud_cover_pct, " %"), value(hour.pressure_msl_hpa, " hPa"), value(hour.uv_index, "", 1)].map((text, i) => <td key={i} className="border-b border-line-soft px-2.5 py-2 text-right">{text}</td>)}
        {forecast.availability?.marine === "available" && <><td className="border-b border-line-soft px-2.5 py-2 text-right">{value(hour.swell, " m", 1)} · {value(hour.period, " s", 1)}</td><td className="border-b border-line-soft px-2.5 py-2 text-right">{value(hour.sst, " °C", 1)}</td></>}
      </tr>; })}</tbody>
    </table></div>}
    {forecast.availability?.marine === "available_stale" && <p role="status" className="px-2 text-label text-muted">Marinewerte stammen vom letzten verfügbaren Stand.</p>}
  </div>;
}
const formatDay = (date: string) => new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
const formatDate = (date: string) => new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
