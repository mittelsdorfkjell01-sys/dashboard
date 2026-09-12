import { Fragment, useMemo } from "react";
import type { LiveConditionsRead } from "../../../lib/api";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { useSpotDataScope, formatWind, windUnitLabel } from "../../../state/SpotDataScope";
import { resolveDirectionSnapshot, degreesToCompass } from "../../../lib/directionSnapshot";
import { referenceMeasurement } from "../../../lib/spotMapReading";
import { sunTimes } from "../../../lib/sunTimes";
import { tempColor } from "../../../lib/tempScale";
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
  // Wave: same source object throughout (selected forecast hour, else live
  // nowcast) — never mix the two for one reading. Headline is total significant
  // wave height when the decomposition is present, else the legacy flat primary
  // swell. The breakdown lists only components the model actually resolved (a
  // flat sea has no wind sea, a single swell no secondary) — never a placeholder.
  const waveComponents = selectedForecast?.waves ?? live?.current?.waves ?? null;
  const flatSwell = selectedForecast?.swell ?? live?.current?.swell ?? null;
  const wave = waveComponents?.total_wave?.significant_height_m ?? flatSwell;
  const waveParts = [
    { label: "Dünung", h: waveComponents?.primary_swell?.significant_height_m },
    { label: "Windsee", h: waveComponents?.wind_sea?.significant_height_m },
    { label: "2. Dünung", h: waveComponents?.secondary_swell?.significant_height_m },
  ].filter((p): p is { label: string; h: number } => p.h != null);
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

  // A nearby station reading is a SEPARATE reference product (P0.1): shown on
  // its own with the real observation time, never merged into the computed
  // reading above. Absent when no accepted measurement exists.
  const reference = referenceMeasurement(live ?? null);
  const referenceStamp = reference
    ? new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(new Date(reference.observedAt)) + " GMT"
    : null;

  // Value/unit split so the reading dominates and the unit reads as quiet
  // metadata (brief: "Der Messwert ist immer wichtiger als seine Einheit").
  // Colour lives only on temperature: GEFÜHLT is tinted on the temperature scale
  // with a faint matching glow; every other reading stays neutral. `value: null`
  // renders an em-dash placeholder for a single missing reading.
  const apparentColor = apparent == null ? undefined : tempColor(apparent);
  const metrics: Array<{ label: string; icon: React.ReactNode; value: string | null; unit?: string; color?: string; glow?: boolean; sub?: React.ReactNode }> = [
    { label: "WIND", icon: <WindIcon />, value: wind == null ? null : formatWind(wind, windUnit), unit: windUnitLabel(windUnit) },
    {
      label: "WELLE", icon: <WaveIcon />, value: wave == null ? null : wave.toFixed(1), unit: "m",
      sub: waveParts.length ? waveParts.map((p, i) => (
        <Fragment key={p.label}>
          {i > 0 && " · "}
          <span className="whitespace-nowrap">{p.label} {p.h.toFixed(1)} m</span>
        </Fragment>
      )) : undefined,
    },
    { label: "UV INDEX", icon: <UvIcon />, value: uv == null ? null : String(Math.round(uv)) },
    { label: "SONNE", icon: <SunIcon />, value: sunHours == null ? null : String(Math.round(sunHours)), unit: "STD" },
    { label: "GEFÜHLT", icon: <TempIcon />, value: apparent == null ? null : `${Math.round(apparent)}°`, color: apparentColor, glow: true },
    { label: "REGEN", icon: <RainIcon />, value: rain == null ? null : rain.toFixed(1), unit: "mm" },
  ];

  return (
    <div className="flex h-full min-w-0 flex-col">
      <p className="border-b border-line pb-3 text-caption tabular-nums text-muted">{stamp}</p>

      <dl className="mt-5 grid grid-cols-2 gap-x-10 gap-y-6">
        {metrics.map(({ label, icon, value, unit, color, glow, sub }) => (
          <div key={label}>
            <dt className="flex items-center gap-1.5 text-caption uppercase tracking-[0.12em] text-muted">
              <span className="text-muted/70" aria-hidden="true">{icon}</span>
              {label}
            </dt>
            <dd className="mt-1.5 flex items-baseline gap-1 text-sz-24 font-semibold tabular-nums text-ink">
              {value == null ? (
                <span className="text-muted">—</span>
              ) : (
                <>
                  <span style={color ? { color, textShadow: glow ? glowShadow(color) : undefined } : undefined}>{value}</span>
                  {unit && <span className="text-caption font-normal text-muted">{unit}</span>}
                </>
              )}
            </dd>
            {sub && value != null && <p className="mt-1 text-caption leading-snug tabular-nums text-muted">{sub}</p>}
          </div>
        ))}
      </dl>

      <div className="mt-10">
        <p className="text-sz-24 font-semibold text-ink">
          {dir == null ? "Richtung —" : `Aus ${degreesToCompass(dir)}`}
        </p>
        {dir != null && <p className="mt-1 text-caption tabular-nums text-muted">{Math.round(dir)} Grad</p>}
        {classLabel && <p className="mt-0.5 text-caption text-muted">{classLabel}</p>}
      </div>

      {reference && (
        <div className="mt-6 border-t border-line pt-3">
          <p className="text-caption uppercase tracking-[0.12em] text-muted">
            Referenzmessung{reference.stationName ? ` · ${reference.stationName}` : ` · ${reference.provider}`}
            {reference.distanceKm != null && (
              <span className="normal-case tracking-normal"> · {reference.distanceKm.toFixed(reference.distanceKm < 10 ? 1 : 0)} km entfernt</span>
            )}
          </p>
          <p className="mt-1 text-caption tabular-nums text-ink">
            <span className="font-semibold">
              {reference.windKt == null ? "—" : `${formatWind(reference.windKt, windUnit)} ${windUnitLabel(windUnit)}`}
            </span>
            {reference.windDir != null && (
              <span className="text-muted"> · aus {degreesToCompass(reference.windDir)} ({Math.round(reference.windDir)} Grad)</span>
            )}
          </p>
          <p className="mt-0.5 text-caption tabular-nums text-muted">Gemessen {referenceStamp}</p>
        </div>
      )}

      {/* Compass hero — pushed to the bottom so its lower edge sits on the map's
          bottom edge; fills the panel's existing inner width. */}
      <div className="mt-auto pt-8">
        <CompassDial fromDeg={dir} />
      </div>
    </div>
  );
}

// A soft glow in the value's own temperature colour (rgb → rgba).
function glowShadow(rgb: string): string {
  return `0 0 14px ${rgb.replace("rgb(", "rgba(").replace(")", ", 0.35)")}`;
}

// Quiet supporting line icons per metric (14px, inherit currentColor). Kept
// minimal so they read as labels, not decoration.
const ICON = { width: 13, height: 13, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.3, strokeLinecap: "round", strokeLinejoin: "round" } as const;
function WindIcon() {
  return (
    <svg {...ICON} aria-hidden="true">
      <path d="M2 5.5h7a1.8 1.8 0 1 0-1.8-1.8" />
      <path d="M2 8.5h9.2a1.9 1.9 0 1 1-1.9 1.9" />
      <path d="M2 11.5h5.5" />
    </svg>
  );
}
function WaveIcon() {
  return (
    <svg {...ICON} aria-hidden="true">
      <path d="M1.5 10c1.6 0 1.6-2.2 3.2-2.2S6.3 10 7.9 10s1.6-2.2 3.2-2.2S12.7 10 14.3 10" />
      <path d="M1.5 6.2c1.6 0 1.6-2.2 3.2-2.2S6.3 6.2 7.9 6.2" opacity="0.6" />
    </svg>
  );
}
function UvIcon() {
  return (
    <svg {...ICON} aria-hidden="true">
      <circle cx="8" cy="8" r="2.6" />
      <path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M12.6 3.4l-1.1 1.1M4.5 11.5l-1.1 1.1" />
    </svg>
  );
}
function SunIcon() {
  return (
    <svg {...ICON} aria-hidden="true">
      <path d="M2 12.5h12" />
      <path d="M4.2 12.5a3.8 3.8 0 0 1 7.6 0" />
      <path d="M8 3v1.5M3.2 5.2l1 1M12.8 5.2l-1 1" opacity="0.7" />
    </svg>
  );
}
function TempIcon() {
  return (
    <svg {...ICON} aria-hidden="true">
      <path d="M6.2 8.6V3.4a1.8 1.8 0 0 1 3.6 0v5.2a3 3 0 1 1-3.6 0Z" />
      <path d="M8 6.5v3.4" />
    </svg>
  );
}
function RainIcon() {
  return (
    <svg {...ICON} aria-hidden="true">
      <path d="M4.4 8.2a2.6 2.6 0 0 1 .3-5.1 3 3 0 0 1 5.7.7 2.3 2.3 0 0 1 .5 4.4" />
      <path d="M5.5 10.5l-.7 1.6M8 10.5l-.7 1.6M10.5 10.5l-.7 1.6" />
    </svg>
  );
}
