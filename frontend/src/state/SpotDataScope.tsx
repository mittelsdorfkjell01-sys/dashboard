import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { closestForecastUtc, forecastHours, selectedForecastHour, type NormalizedForecastHour, type NormalizedForecastSeries } from "../lib/forecastNormalization";

export type SportMode = "wind" | "surf";
export type WindUnit = "kts" | "ms";
export type MapLayer = "wind" | "both" | "wave";

type SpotDataScopeValue = {
  selectedAtUtc: string | null;
  setSelectedAtUtc: (instant: string | null) => void;
  selectedForecast: NormalizedForecastHour | null;
  availableForecasts: NormalizedForecastHour[];
  forecastTimezone: string;
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
  const availableForecasts = useMemo(() => forecastHours(forecast), [forecast]);
  const [selectedAtUtc, setSelectedAtUtc] = useState<string | null>(null);
  const [sportMode, setSportModeState] = useState<SportMode>(() =>
    storedChoice("sw-sport-mode", ["wind", "surf"], "wind"),
  );
  const [windUnit, setWindUnitState] = useState<WindUnit>(() =>
    storedChoice("sw-wind-unit", ["kts", "ms"], "kts"),
  );
  const [mapLayer, setMapLayer] = useState<MapLayer>("both");

  useEffect(() => {
    setSelectedAtUtc((current) => {
      if (current && availableForecasts.some((hour) => hour.utcKey === current)) return current;
      return closestForecastUtc(forecast);
    });
  }, [availableForecasts, forecast]);

  const selectedForecast = useMemo(
    () => selectedForecastHour(forecast, selectedAtUtc),
    [forecast, selectedAtUtc],
  );

  const selectForecastAt=useCallback((instant:string|null)=>setSelectedAtUtc(resolveForecastSelection(availableForecasts,instant)),[availableForecasts]);
  const value = useMemo<SpotDataScopeValue>(() => ({
    selectedAtUtc,
    setSelectedAtUtc: selectForecastAt,
    selectedForecast,
    availableForecasts,
    forecastTimezone: forecast?.timezone ?? "UTC",
    sportMode,
    setSportMode: (mode) => {
      setSportModeState(mode);
      window.localStorage.setItem("sw-sport-mode", mode);
    },
    windUnit,
    setWindUnit: (unit) => {
      setWindUnitState(unit);
      window.localStorage.setItem("sw-wind-unit", unit);
    },
    mapLayer,
    setMapLayer,
  }), [availableForecasts, forecast?.timezone, mapLayer, selectForecastAt, selectedAtUtc, selectedForecast, sportMode, windUnit]);

  return <SpotDataContext.Provider value={value}>{children}</SpotDataContext.Provider>;
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

export function formatWind(kts: number, unit: WindUnit): string {
  return unit === "ms" ? (kts * 0.514444).toFixed(1) : String(Math.round(kts));
}

export function windUnitLabel(unit: WindUnit): string {
  return unit === "ms" ? "m/s" : "kts";
}
