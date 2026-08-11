import type { ForecastSeries } from "../../lib/api";

export default function WeatherDetailsTable({ forecast }: { forecast: ForecastSeries }) {
  if (!forecast.days.length) return null;
  // TODO(backend): feelTemp, cloudCover, uv, pressure, sunrise and sunset ergänzen.
  return (
    <div className="overflow-x-auto px-2 pb-2">
      <table className="min-w-[620px] w-full border-collapse text-ui tabular-nums">
        <thead><tr>{["Tag", "Temp", "Gefühlt", "Regen", "Wolken", "UV", "Druck", "Sonne"].map((label) => <th key={label} className="border-b border-line px-2.5 py-1.5 text-left text-caption font-medium uppercase tracking-wide text-muted first:w-[90px] [&:not(:first-child)]:text-right">{label}</th>)}</tr></thead>
        <tbody>{forecast.days.slice(0, 7).map((day, index) => {
          const rain = day.hours.reduce((sum, hour) => sum + (hour.precip ?? 0), 0);
          return <tr key={day.date} className={`transition-colors hover:bg-band ${index === 0 ? "bg-band" : ""}`}>
            <td className="border-b border-line-soft px-2.5 py-1.5 font-medium text-ink">{formatDay(day.date)} <span className="font-light text-muted">{formatDate(day.date)}</span></td>
            <td className="border-b border-line-soft px-2.5 py-1.5 text-right text-ink">{show(day.summary.air_max)} / <span className="text-muted">{show(day.summary.air_min)}</span> °C</td>
            <td className="border-b border-line-soft px-2.5 py-1.5 text-right text-muted">-</td>
            <td className="border-b border-line-soft px-2.5 py-1.5 text-right text-ink">{rain > 0 ? `${rain.toFixed(1)} mm` : "-"}</td>
            <td className="border-b border-line-soft px-2.5 py-1.5 text-right text-muted">-</td><td className="border-b border-line-soft px-2.5 py-1.5 text-right text-muted">-</td><td className="border-b border-line-soft px-2.5 py-1.5 text-right text-muted">-</td><td className="border-b border-line-soft px-2.5 py-1.5 text-right text-muted">-</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}
const show = (value: number | null) => value == null ? "-" : Math.round(value);
const formatDay = (date: string) => new Intl.DateTimeFormat("de-DE", { weekday: "short" }).format(new Date(`${date}T12:00:00`));
const formatDate = (date: string) => new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" }).format(new Date(`${date}T12:00:00`));
