import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type SportMode = "wind" | "surf";
export type WindUnit = "kts" | "ms";
export type MapLayer = "wind" | "both" | "wave";

type SpotDataScopeValue = {
  selectedHour: number;
  setSelectedHour: (hour: number) => void;
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

export function SpotDataScopeProvider({ children }: { children: ReactNode }) {
  const [selectedHour, setSelectedHourState] = useState(() => new Date().getHours());
  const [sportMode, setSportModeState] = useState<SportMode>(() =>
    storedChoice("sw-sport-mode", ["wind", "surf"], "wind"),
  );
  const [windUnit, setWindUnitState] = useState<WindUnit>(() =>
    storedChoice("sw-wind-unit", ["kts", "ms"], "kts"),
  );
  const [mapLayer, setMapLayer] = useState<MapLayer>("both");

  const value = useMemo<SpotDataScopeValue>(() => ({
    selectedHour,
    setSelectedHour: (hour) => setSelectedHourState(Math.max(0, Math.min(23, Math.round(hour)))),
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
  }), [mapLayer, selectedHour, sportMode, windUnit]);

  return <SpotDataContext.Provider value={value}>{children}</SpotDataContext.Provider>;
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
