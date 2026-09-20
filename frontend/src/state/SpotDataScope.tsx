import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { selectedForecastHour, type NormalizedForecastHour, type NormalizedForecastSeries } from "../lib/forecastNormalization";
import { spotForecastHours } from "../lib/spotForecastWindow";
import { useOptionalPrefs } from "../context/PrefsContext";
import { DEFAULT_UNITS, windValue, WIND_UNIT_SUFFIX, type WindUnit } from "../lib/units";

export type SportMode = "wind" | "surf";
// Wind unit is owned by PrefsContext (the single source of truth); re-exported
// here so the Daten components can keep importing it from the scope.
export type { WindUnit };
// "waves" colors by primary swell — see docs/map-redesign-backend-gaps.md
// for why total-wave/wind-sea decomposition isn't offered as its own layer
// yet. No "both" mode: the redesign shows one focused layer at a time
// rather than all animation simultaneously (see the map redesign brief).
export type MapLayer = "wind" | "waves";
export type WeatherTimeMode = "now" | "forecast";

type SpotDataScopeValue = {
  selectedAtUtc: string | null;
  setSelectedAtUtc: (instant: string | null) => void;
  selectedForecast: NormalizedForecastHour | null;
  weatherTimeMode: WeatherTimeMode;
  availableForecasts: NormalizedForecastHour[];
  forecastTimezone: string;
  forecastStale: boolean;
  forecastModel: string | null;
  sportMode: SportMode;
  setSportMode: (mode: SportMode) => void;
  windUnit: WindUnit;
  setWindUnit: (unit: WindUnit) => void;
  mapLayer: MapLayer;
  setMapLayer: (layer: MapLayer) => void;
};

const SpotDataContext = createContext<SpotDataScopeValue | null>(null);

function storedChoice<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  if (typeof window === "undefined") return fallback;
  const value = window.localStorage.getItem(key) as T | null;
  return value && allowed.includes(value) ? value : fallback;
}

export function SpotDataScopeProvider({ children, forecast = null }: { children: ReactNode; forecast?: NormalizedForecastSeries | null }) {
  const availableForecasts = useMemo(() => spotForecastHours(forecast), [forecast]);
  const [selectedAtUtc, setSelectedAtUtc] = useState<string | null>(null);
  const [weatherTimeMode, setWeatherTimeMode] = useState<WeatherTimeMode>("now");
  const [sportMode, setSportModeState] = useState<SportMode>(() =>
    storedChoice("sw-sport-mode", ["wind", "surf"], "wind"),
  );
  // Wind unit comes from the shared display preferences (PrefsContext), so the
  // Daten page honours the account settings and vice-versa. `useOptionalPrefs`
  // keeps the scope usable in isolated tests that mount it without the provider.
  const prefs = useOptionalPrefs();
  const windUnit: WindUnit = prefs?.units.wind ?? DEFAULT_UNITS.wind;
  const setWindUnit = useCallback((unit: WindUnit) => prefs?.setUnit("wind", unit), [prefs]);
  const [mapLayer, setMapLayer] = useState<MapLayer>("wind");

  useEffect(() => {
    setSelectedAtUtc((current) => {
      return resolveForecastSelection(availableForecasts, current);
    });
    if (!availableForecasts.length) setWeatherTimeMode("now");
  }, [availableForecasts]);

  const selectedForecast = useMemo(
    () => selectedForecastHour(forecast, selectedAtUtc),
    [forecast, selectedAtUtc],
  );

  const selectForecastAt = useCallback((instant: string | null) => {
    setWeatherTimeMode(instant == null ? "now" : "forecast");
    setSelectedAtUtc(resolveForecastSelection(availableForecasts, instant));
  }, [availableForecasts]);
  const value = useMemo<SpotDataScopeValue>(() => ({
    selectedAtUtc,
    setSelectedAtUtc: selectForecastAt,
    selectedForecast,
    weatherTimeMode,
    availableForecasts,
    forecastTimezone: forecast?.timezone ?? "UTC",
    forecastStale: forecast?.stale === true,
    forecastModel: forecast?.model ?? null,
    sportMode,
    setSportMode: (mode) => {
      setSportModeState(mode);
      window.localStorage.setItem("sw-sport-mode", mode);
    },
    windUnit,
    setWindUnit,
    mapLayer,
    setMapLayer,
  }), [availableForecasts, forecast?.model, forecast?.stale, forecast?.timezone, mapLayer, selectForecastAt, selectedAtUtc, selectedForecast, sportMode, setWindUnit, weatherTimeMode, windUnit]);

  return <SpotDataContext.Provider value={value}>{children}</SpotDataContext.Provider>;
}

/** Only an explicit chart/scrubber selection may switch the display product
 * from the current analysis to a forecast hour. The cursor can still rest on
 * the nearest forecast slot while the visible mode remains "now". */
export function displayedForecast(
  mode: WeatherTimeMode,
  selected: NormalizedForecastHour | null,
): NormalizedForecastHour | null {
  return mode === "forecast" ? selected : null;
}

export function resolveForecastSelection(hours:NormalizedForecastHour[], requested:string|null, now=Date.now()):string|null {
  if(!hours.length)return null;
  if(requested&&hours.some((hour)=>hour.utcKey===requested))return requested;
  const target=requested&&Number.isFinite(Date.parse(requested))?Date.parse(requested):now;
  return hours.reduce((best,hour)=>Math.abs(Date.parse(hour.utcKey)-target)<Math.abs(Date.parse(best.utcKey)-target)?hour:best).utcKey;
}

export function useSpotDataScope(): SpotDataScopeValue {
  const value = useContext(SpotDataContext);
  if (!value) throw new Error("useSpotDataScope must be inside SpotDataScopeProvider");
  return value;
}

export function useOptionalSpotDataScope(): SpotDataScopeValue | null {
  return useContext(SpotDataContext);
}

// Numeric wind reading in the active unit (no suffix); the suffix comes from
// windUnitLabel so call sites render "{value} {label}". Delegates to lib/units
// so knots/Beaufort/metres-per-second all format consistently app-wide.
export function formatWind(kn: number, unit: WindUnit): string {
  return windValue(kn, unit);
}

export function windUnitLabel(unit: WindUnit): string {
  return WIND_UNIT_SUFFIX[unit];
}
