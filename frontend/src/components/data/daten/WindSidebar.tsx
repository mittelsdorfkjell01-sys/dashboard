import { Fragment, useEffect, useMemo, useState } from "react";
import type { LiveConditionsRead } from "../../../lib/api";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { displayedForecast, useSpotDataScope, windUnitLabel, type WindUnit } from "../../../state/SpotDataScope";
import { resolveDirectionSnapshot, degreesToCompass } from "../../../lib/directionSnapshot";
import { referenceMeasurement } from "../../../lib/spotMapReading";
import {
  currentWindPresentation,
  displayDirectionDeg,
  formatAge,
  uncertaintyBandKt,
  VARIABLE_WIND_THRESHOLD_MS,
} from "../../../lib/liveWindPresentation";
import { sunTimes } from "../../../lib/sunTimes";
import { tempColor } from "../../../lib/tempScale";
import { useOptionalUnits } from "../../../context/PrefsContext";
import {
  waveValue,
  WAVE_UNIT_SUFFIX,
  tempValue,
  TEMP_UNIT_SUFFIX,
  distanceValue,
  DISTANCE_UNIT_SUFFIX,
  windValue,
} from "../../../lib/units";
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
  liveLoading = false,
  liveError = null,
  liveStale = false,
  onRetryLive,
  lat,
  lng,
}: {
  forecast: NormalizedForecastSeries | null;
  live?: LiveConditionsRead | null;
  liveLoading?: boolean;
  liveError?: string | null;
  liveStale?: boolean;
  onRetryLive?: () => void;
  lat?: number;
  lng?: number;
}) {
  const {
    selectedForecast,
    setSelectedAtUtc,
    weatherTimeMode,
    windUnit,
    forecastTimezone,
    forecastStale,
    forecastModel,
  } = useSpotDataScope();
  const units = useOptionalUnits();
  const activeForecast = displayedForecast(weatherTimeMode, selectedForecast);
  const snapshot = resolveDirectionSnapshot({ selectedForecast: activeForecast, live, forecastTimezone, forecastStale, forecastModel });
  const currentWind = currentWindPresentation(live);
  const online = useOnlineStatus();
  const forecastMode = activeForecast !== null;

  const day = useMemo(() => {
    if (!activeForecast) return null;
    return forecast?.days.find((d) => (d.local_date ?? d.date) === activeForecast.localDate) ?? null;
  }, [activeForecast, forecast?.days]);

  const wind = snapshot?.windKt ?? null;
  // Wave: same source object throughout (selected forecast hour, else live
  // nowcast) — never mix the two for one reading. Headline is total significant
  // wave height when the decomposition is present, else the legacy flat primary
  // swell. The breakdown lists only components the model actually resolved (a
  // flat sea has no wind sea, a single swell no secondary) — never a placeholder.
  const waveComponents = activeForecast ? activeForecast.waves ?? null : live?.current?.waves ?? null;
  const flatSwell = activeForecast ? activeForecast.swell : live?.current?.swell ?? null;
  const wave = waveComponents?.total_wave?.significant_height_m ?? flatSwell;
  const waveParts = [
    { label: "Dünung", h: waveComponents?.primary_swell?.significant_height_m },
    { label: "Windsee", h: waveComponents?.wind_sea?.significant_height_m },
    { label: "2. Dünung", h: waveComponents?.secondary_swell?.significant_height_m },
  ].filter((p): p is { label: string; h: number } => p.h != null);
  const uv = activeForecast?.uv_index ?? day?.summary.uv_index_max ?? null;
  const apparent = activeForecast?.apparent_temperature_c ?? day?.summary.apparent_temperature_max_c ?? null;
  const rain = activeForecast?.precip ?? day?.summary.precipitation_sum_mm ?? null;

  const sunHours = useMemo(() => {
    if (lat == null || lng == null) return null;
    const sun = sunTimes(lat, lng, new Date());
    return sun ? sun.sunset - sun.sunrise : null;
  }, [lat, lng]);

  const validAt = activeForecast?.time ?? currentWind.analyzedAt;
  const stamp = formatInstant(validAt, forecastMode ? forecastTimezone : "UTC");

  const dir = snapshot?.windDirectionFromDeg ?? null;
  const classification = snapshot?.windCoastalClassification;
  const classLabel = classification && classification !== "unavailable" ? CLASS_LABEL[classification] : null;

  // A nearby station reading is a SEPARATE reference product (P0.1): shown on
  // its own with the real observation time, never merged into the computed
  // reading above. Absent when no accepted measurement exists.
  const reference = forecastMode ? null : referenceMeasurement(live ?? null);
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
    { label: "WIND", icon: <WindIcon />, value: wind == null ? null : formatWindReading(wind, windUnit), unit: windUnitLabel(windUnit) },
    {
      label: "WELLE", icon: <WaveIcon />, value: wave == null ? null : waveValue(wave, units.wave), unit: WAVE_UNIT_SUFFIX[units.wave],
      sub: waveParts.length ? waveParts.map((p, i) => (
        <Fragment key={p.label}>
          {i > 0 && " · "}
          <span className="whitespace-nowrap">{p.label} {waveValue(p.h, units.wave)} {WAVE_UNIT_SUFFIX[units.wave]}</span>
        </Fragment>
      )) : undefined,
    },
    { label: "UV INDEX", icon: <UvIcon />, value: uv == null ? null : String(Math.round(uv)) },
    { label: "SONNE", icon: <SunIcon />, value: sunHours == null ? null : String(Math.round(sunHours)), unit: "STD" },
    { label: "GEFÜHLT", icon: <TempIcon />, value: apparent == null ? null : tempValue(apparent, units.temp), unit: TEMP_UNIT_SUFFIX[units.temp], color: apparentColor, glow: true },
    { label: "REGEN", icon: <RainIcon />, value: rain == null ? null : rain.toFixed(1), unit: "mm" },
  ];
  const uncertainty = uncertaintyBandKt(currentWind);
  const directionState = forecastMode
    ? wind != null && wind * 0.514444 < VARIABLE_WIND_THRESHOLD_MS
      ? "variable"
      : dir == null
        ? "unavailable"
        : "known"
    : currentWind.directionState;
  const currentStale = !forecastMode && (liveStale || currentWind.stale);
  const forecastIsStale = forecastMode && (forecastStale || activeForecast?.stale === true);
  const noCurrentData = !forecastMode && currentWind.status === "unavailable";
  const currentLoading = noCurrentData && liveLoading;
  const currentOffline = !forecastMode && !online;

  return (
    <div
      data-weather-time-mode={forecastMode ? "forecast" : "now"}
      data-live-wind-status={forecastMode ? undefined : currentWind.status}
      className="flex h-full min-w-0 flex-col"
    >
      <div className="border-b border-line pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-ui font-semibold text-ink">
            {forecastMode ? "Forecast" : "Aktuelle Bedingungen"}
          </h2>
          {forecastMode ? (
            <button
              type="button"
              onClick={() => setSelectedAtUtc(null)}
              className="rounded-full border border-line px-2.5 py-1 text-caption font-semibold text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              Jetzt
            </button>
          ) : (
            <span className={`rounded-full px-2.5 py-1 text-caption font-semibold ${currentWind.status === "station_adjusted" ? "bg-green/15 text-green" : "bg-band text-ink-soft"}`}>
              {currentWind.statusLabel}
            </span>
          )}
        </div>

        {currentLoading ? (
          <div role="status" aria-live="polite" className="mt-3 space-y-2">
            <span className="sr-only">Aktuelle Bedingungen werden geladen.</span>
            <span aria-hidden className="block h-3 w-4/5 animate-pulse rounded bg-line" />
            <span aria-hidden className="block h-3 w-3/5 animate-pulse rounded bg-line" />
          </div>
        ) : (
          <p className="mt-2 text-caption tabular-nums text-muted">
            {forecastMode ? "Gültig" : "Analysiert"} {stamp}
            {!forecastMode && currentWind.ageMinutes != null && ` · ${formatAge(currentWind.ageMinutes)}`}
          </p>
        )}

        {!forecastMode && !currentLoading && (
          <dl className="mt-3 grid grid-cols-2 gap-x-5 gap-y-2 text-caption">
            <div>
              <dt className="text-muted">Unsicherheitsband</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-ink">
                {uncertainty
                  ? `${formatWindReading(uncertainty[0], windUnit)}–${formatWindReading(uncertainty[1], windUnit)} ${windUnitLabel(windUnit)}`
                  : "Nicht bestimmt"}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Relevante Stationen</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-ink">{currentWind.stationCount}</dd>
            </div>
          </dl>
        )}

        {!forecastMode && currentWind.status === "baseline" && currentWind.fallbackReason && (
          <p className="mt-3 text-caption leading-relaxed text-muted">{currentWind.fallbackReason}</p>
        )}
        {!forecastMode && noCurrentData && !currentLoading && (
          <p role="alert" className="mt-3 text-caption leading-relaxed text-orange">
            {currentOffline
              ? "Offline: Es ist keine gespeicherte aktuelle Analyse verfügbar."
              : liveError || currentWind.fallbackReason}
          </p>
        )}
        {!forecastMode && liveError && !noCurrentData && (
          <p role="status" className="mt-3 text-caption leading-relaxed text-orange">
            {currentOffline ? "Offline: Gespeicherte Analyse wird weiter angezeigt." : "Aktualisierung fehlgeschlagen; die letzte Analyse bleibt sichtbar."}
          </p>
        )}
        {!forecastMode && currentOffline && !noCurrentData && !liveError && (
          <p role="status" className="mt-3 text-caption leading-relaxed text-orange">
            Offline: Die zuletzt geladene Analyse wird weiter angezeigt.
          </p>
        )}
        {(currentStale || forecastIsStale) && (
          <p role="alert" className="mt-3 text-caption leading-relaxed text-orange">
            {forecastMode ? "Dieser Forecast ist veraltet." : "Diese Analyse ist veraltet und nur als Orientierung geeignet."}
          </p>
        )}
        {!forecastMode && (noCurrentData || liveError) && onRetryLive && online && (
          <button
            type="button"
            onClick={onRetryLive}
            className="mt-3 text-caption font-semibold text-ink underline decoration-line underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Aktuelle Bedingungen erneut laden
          </button>
        )}
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5 sm:gap-x-10 sm:gap-y-6">
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

      {reference && (
        <div className="mt-6 border-t border-line pt-3">
          <p className="text-caption uppercase tracking-[0.12em] text-muted">
            Referenzmessung{reference.stationName ? ` · ${reference.stationName}` : ` · ${reference.provider}`}
            {reference.distanceKm != null && (
              <span className="normal-case tracking-normal"> · {distanceValue(reference.distanceKm, units.distance)} {DISTANCE_UNIT_SUFFIX[units.distance]} entfernt</span>
            )}
          </p>
          <p className="mt-1 text-caption tabular-nums text-ink">
            <span className="font-semibold">
              {reference.windKt == null ? "—" : `${formatWindReading(reference.windKt, windUnit)} ${windUnitLabel(windUnit)}`}
            </span>
            {reference.windMs != null && reference.windMs < VARIABLE_WIND_THRESHOLD_MS ? (
              <span className="text-muted"> · variabel</span>
            ) : reference.windDir != null && (
              <span className="text-muted"> · aus {degreesToCompass(reference.windDir)} ({displayDirectionDeg(reference.windDir)} Grad)</span>
            )}
          </p>
          <p className="mt-0.5 text-caption tabular-nums text-muted">Gemessen {referenceStamp}</p>
        </div>
      )}

      {/* Compass hero — pushed to the bottom so its lower edge sits on the map's
          bottom edge; fills the panel's existing inner width. The direction now
          reads as a compact caption under the dial instead of a large heading
          above the metrics (removed on request). */}
      <div className="mt-auto pt-8">
        <CompassDial fromDeg={directionState === "known" ? dir : null} />
        <p className="mt-3 text-center text-caption tabular-nums text-muted">
          {directionState === "variable" ? (
            "Wind variabel"
          ) : directionState === "uncertain" ? (
            "Richtung unsicher"
          ) : dir == null ? (
            "Richtung —"
          ) : (
            <>
              <span className="font-semibold text-ink">Aus {degreesToCompass(dir)}</span>
              {` · ${displayDirectionDeg(dir)}°`}
              {classLabel ? ` · ${classLabel}` : ""}
            </>
          )}
        </p>
      </div>
    </div>
  );
}

function formatInstant(instant: string | null, timezone: string): string {
  if (!instant || !Number.isFinite(Date.parse(instant))) return "Zeit unbekannt";
  try {
    const value = new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: timezone,
      timeZoneName: "short",
    }).format(new Date(instant));
    return value;
  } catch {
    return new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
      timeZoneName: "short",
    }).format(new Date(instant));
  }
}

function formatWindReading(windKt: number, unit: WindUnit): string {
  return windValue(windKt, unit);
}

function useOnlineStatus(): boolean {
  // Keep SSR and the first hydrated frame deterministic. The real browser
  // state is synchronized immediately after mount, including a pre-existing
  // offline state that did not emit an event while this component existed.
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const markOnline = () => setOnline(true);
    const markOffline = () => setOnline(false);
    setOnline(navigator.onLine);
    window.addEventListener("online", markOnline);
    window.addEventListener("offline", markOffline);
    return () => {
      window.removeEventListener("online", markOnline);
      window.removeEventListener("offline", markOffline);
    };
  }, []);
  return online;
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
