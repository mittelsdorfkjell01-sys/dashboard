import type { ForecastHour, LiveConditionsRead } from "../../lib/api";
import { formatWind, useSpotDataScope, windUnitLabel } from "../../state/SpotDataScope";

type Source = ForecastHour | LiveConditionsRead["current"] | null;
type Cell = { label: string; value: string; unit: string; sub: string; priority?: boolean };

const number = (source: Source, ...keys: string[]): number | null => {
  if (!source) return null;
  for (const key of keys) {
    const value = (source as unknown as Record<string, unknown>)[key];
    if (typeof value === "number") return value;
  }
  return null;
};

export default function LiveRow({ live }: {
  live?: LiveConditionsRead | null;
}) {
  const { selectedForecast, windUnit, sportMode } = useSpotDataScope();
  const source: Source = selectedForecast ?? live?.current ?? null;
  const wind = number(source, "wind");
  const gust = number(source, "gust");
  const wave = number(source, "swell", "waveHeight");
  const period = number(source, "period");
  const direction = number(source, "dir");
  const waveDirection = number(source, "swell_dir", "waveDir");
  const water = number(source, "sst", "waterTemp");
  const air = number(source, "air", "airTemp");

  const windCell = { label: "Wind", value: wind == null ? "-" : formatWind(wind, windUnit), unit: windUnitLabel(windUnit), sub: direction == null ? "" : `↗ ${Math.round(direction)}°`, priority: true };
  const waveCell = { label: "Welle", value: wave == null ? "-" : wave.toFixed(1), unit: "m", sub: `${period == null ? "-" : Math.round(period)} s · ${waveDirection == null ? "-" : formatDirection(waveDirection)}`, priority: sportMode === "surf" };
  const cells: Cell[] = sportMode === "surf"
    ? [
        waveCell,
        { label: "Periode", value: period == null ? "-" : String(Math.round(period)), unit: "s", sub: waveDirection == null ? "" : `↖ ${Math.round(waveDirection)}°` },
        { ...windCell, priority: false },
        { label: "Tide", value: "-", unit: "", sub: "" },
        { label: "Wasser", value: water == null ? "-" : String(Math.round(water)), unit: "°C", sub: "" },
        { label: "Luft", value: air == null ? "-" : String(Math.round(air)), unit: "°C", sub: "" },
      ]
    : [
        windCell,
        { label: "Böen", value: gust == null ? "-" : formatWind(gust, windUnit), unit: windUnitLabel(windUnit), sub: gust != null && wind != null ? `Δ +${formatWind(Math.max(0, gust - wind), windUnit)}` : "" },
        waveCell,
        { label: "Wasser", value: water == null ? "-" : String(Math.round(water)), unit: "°C", sub: "" },
        { label: "Luft", value: air == null ? "-" : String(Math.round(air)), unit: "°C", sub: "" },
        { label: "Tide", value: "-", unit: "", sub: "" },
      ];

  return (
    <div data-forecast-utc={selectedForecast?.utcKey??""} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
      {cells.map((cell) => (
        <div key={cell.label} className={`border-b border-r border-line-soft px-3 py-2.5 text-right lg:border-b-0 ${cell.priority ? "bg-gradient-to-b from-green/[0.06] to-transparent" : ""}`}>
          <p className="mb-1.5 text-left text-caption font-medium uppercase tracking-widest text-muted">{cell.label}</p>
          <p><span className="text-title font-medium leading-none tabular-nums text-ink">{cell.value}</span>{cell.unit && <span className="ml-0.5 text-caption text-muted">{cell.unit}</span>}</p>
          {cell.sub && <p className="mt-1 text-left text-caption text-muted">{cell.sub}</p>}
        </div>
      ))}
    </div>
  );
}

function formatDirection(degrees: number): string {
  const directions = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"];
  return directions[Math.round(degrees / 45) % 8];
}
