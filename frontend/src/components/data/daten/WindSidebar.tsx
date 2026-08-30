import { useMemo } from "react";
import type { LiveConditionsRead } from "../../../lib/api";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { resolveDirectionSnapshot, degreesToCompass } from "../../../lib/directionSnapshot";
import { sunTimes } from "../../../lib/sunTimes";
import CompassDial from "./CompassDial";

const CLASS_LABEL: Record<string, string> = {
  onshore: "Onshore",
  cross_onshore: "Cross-onshore",
  sideshore: "Sideshore",
  cross_offshore: "Cross-offshore",
  offshore: "Offshore",
};

/**
 * Right column of the Daten-page map band (Figma Frame 67): the reading's
 * timestamp, a 2×3 live-metric grid (wind, wave, UV, sun hours, apparent
 * temperature, rain), and the wind direction with a compass dial. Everything
 * is read from the shared selection / live conditions — nothing synthetic.
 */
export default function WindSidebar({
  forecast,
  live,
  lat,
  lng,
}: {
  forecast: NormalizedForecastSeries | null;
  live?: LiveConditionsRead | null;
  lat?: number;
  lng?: number;
}) {
  const { selectedForecast, windUnit, forecastTimezone, forecastStale, forecastModel } = useSpotDataScope();
  const snapshot = resolveDirectionSnapshot({ selectedForecast, live, forecastTimezone, forecastStale, forecastModel });

  const day = useMemo(() => {
    const date = selectedForecast?.localDate;
    return forecast?.days.find((d) => (d.local_date ?? d.date) === date) ?? forecast?.days[0] ?? null;
  }, [forecast?.days, selectedForecast?.localDate]);

  const wind = snapshot?.windKt ?? null;
  const wave = selectedForecast?.swell ?? live?.current?.swell ?? null;
  const uv = selectedForecast?.uv_index ?? day?.summary.uv_index_max ?? null;
  const apparent = selectedForecast?.apparent_temperature_c ?? day?.summary.apparent_temperature_max_c ?? null;
  const rain = selectedForecast?.precip ?? day?.summary.precipitation_sum_mm ?? null;

  const sunHours = useMemo(() => {
    if (lat == null || lng == null) return null;
    const sun = sunTimes(lat, lng, new Date());
    return sun ? sun.sunset - sun.sunrise : null;
  }, [lat, lng]);

  const validAt = selectedForecast?.time ?? live?.time ?? null;
  const stamp = validAt
    ? new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(new Date(validAt)) + " GMT"
    : "Zeit unbekannt";

  const dir = snapshot?.windDirectionFromDeg ?? null;
  const classification = snapshot?.windCoastalClassification;
  const classLabel = classification && classification !== "unavailable" ? CLASS_LABEL[classification] : null;

  const metrics: Array<[string, string]> = [
    ["WIND", wind == null ? "–" : `${formatWind(wind, windUnit)} ${windUnitLabel(windUnit)}`],
    ["WELLE", wave == null ? "–" : `${wave.toFixed(1)} m`],
    ["UV INDEX", uv == null ? "–" : String(Math.round(uv))],
    ["SONNE", sunHours == null ? "–" : `${Math.round(sunHours)} STD`],
    ["GEFÜHLT", apparent == null ? "–" : `${Math.round(apparent)} C`],
    ["REGEN", rain == null ? "–" : `${rain.toFixed(1)} mm`],
  ];

  return (
    <div className="flex min-w-0 flex-col">
      <p className="border-b border-line pb-3 text-caption tabular-nums text-muted">{stamp}</p>

      <dl className="mt-5 grid grid-cols-2 gap-x-10 gap-y-6">
        {metrics.map(([label, value]) => (
          <div key={label}>
            <dt className="text-caption uppercase tracking-[0.12em] text-muted">{label}</dt>
            <dd className="mt-1.5 text-sz-24 font-semibold tabular-nums text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-10">
        <p className="text-sz-24 font-semibold text-ink">
          {dir == null ? "Richtung –" : `Aus ${degreesToCompass(dir)}`}
        </p>
        {dir != null && <p className="mt-1 text-caption tabular-nums text-muted">{Math.round(dir)} Grad</p>}
        {classLabel && <p className="mt-0.5 text-caption text-muted">{classLabel}</p>}
      </div>

      <div className="mt-6">
        <CompassDial fromDeg={dir} />
      </div>
    </div>
  );
}
