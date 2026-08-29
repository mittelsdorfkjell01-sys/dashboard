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
  // Keep the row on exactly the same data kind as DirectionCompass/SpotMap.
  // A station measurement contains wind only; missing weather fields remain
  // missing instead of being silently borrowed from the model nowcast.
  const measurementSource: Source = !selectedForecast && live?.measurement ? {
    wind: live.measurement.wind_speed_ms == null ? null : live.measurement.wind_speed_ms / 0.514444,
    gust: live.measurement.wind_gust_ms == null ? null : live.measurement.wind_gust_ms / 0.514444,
    dir: live.measurement.wind_direction_from_deg,
    air: null, sst: null, swell: null, period: null, swell_dir: null,
  } : null;
  const source: Source = selectedForecast ?? measurementSource ?? live?.current ?? null;
  const provenance = selectedForecast?.provenance ?? live?.sources?.wind ?? live?.provenance ?? null;
  const sourceLabel = selectedForecast ? "Ausgewählte Forecaststunde"
    : provenance?.source_type === "measurement" ? "Stationsmessung" : "Aktuell · berechnet";
  const validAt = selectedForecast?.time ?? provenance?.valid_at ?? live?.time ?? null;
  const ageLabel = provenance?.age_seconds == null ? "Alter unbekannt"
    : provenance.age_seconds < 60 ? "vor weniger als 1 Minute"
    : `vor ${Math.floor(provenance.age_seconds / 60)} Minuten`;
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
    <section aria-label="Wetterwerte und Herkunft">
      <div className="flex flex-wrap items-start justify-between gap-2 px-3 py-3 text-label">
        <div>
          <p className="font-semibold text-ink">{sourceLabel}</p>
          <p className="mt-0.5 text-muted">{validAt ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(validAt)) : "Datenzeit unbekannt"}{!selectedForecast && ` · ${ageLabel}`}</p>
        </div>
        <details className="max-w-prose text-muted">
          <summary className="cursor-pointer font-medium text-teal underline-offset-4 hover:underline">Herkunft erklären</summary>
          <p className="mt-2">{provenance?.provider ?? "Surfwinddata"}. Modelllaufzeit: {provenance?.model_run_at ? "bekannt" : "nicht vom Provider gemeldet"}. Wind, Luft und Marinewerte können unterschiedliche Quellen haben.</p>
          {live?.measurement && !selectedForecast && <p className="mt-2">Station {live.measurement.station_name ?? live.measurement.provider_station_id} · {live.measurement.distance_km == null ? "Entfernung unbekannt" : `${live.measurement.distance_km.toFixed(1)} km vom Spot`}. Die Station steht nicht zwingend direkt am Spot.</p>}
        </details>
      </div>
      {(provenance?.stale || selectedForecast?.stale) && <p role="alert" className="border-y border-warning/40 bg-warning/10 px-3 py-2 text-label font-medium text-ink">Diese Daten sind veraltet. Bitte nutze sie nicht als aktuelle Lageeinschätzung.</p>}
    <div data-forecast-utc={selectedForecast?.utcKey??""} data-source-type={provenance?.source_type ?? "unknown"} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
      {cells.map((cell) => (
        <div key={cell.label} className={`border-b border-r border-line-soft px-3 py-2.5 text-right lg:border-b-0 ${cell.priority ? "bg-gradient-to-b from-green/[0.06] to-transparent" : ""}`}>
          <p className="mb-1.5 text-left text-caption font-medium uppercase tracking-widest text-muted">{cell.label}</p>
          <p><span className="text-title font-medium leading-none tabular-nums text-ink">{cell.value}</span>{cell.unit && <span className="ml-0.5 text-caption text-muted">{cell.unit}</span>}</p>
          {cell.sub && <p className="mt-1 text-left text-caption text-muted">{cell.sub}</p>}
        </div>
      ))}
    </div>
    </section>
  );
}

function formatDirection(degrees: number): string {
  const directions = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"];
  return directions[Math.round(degrees / 45) % 8];
}
