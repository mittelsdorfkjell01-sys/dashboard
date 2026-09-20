import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { DEFAULT_UNITS, normalizeWindUnit, type Units } from "../lib/units";

interface PrefsValue {
  units: Units;
  setUnit: <K extends keyof Units>(key: K, value: Units[K]) => void;
}

const KEY = "swd.prefs";
// The Daten page used to keep its own wind unit here before the systems merged.
const LEGACY_WIND_KEY = "sw-wind-unit";

function load(): Units {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw);
      const stored = (p.units ?? p ?? {}) as Partial<Units>;
      const merged = { ...DEFAULT_UNITS, ...stored };
      // Adopt a pre-merge Daten-page wind choice if this store never had one.
      if (stored.wind == null) {
        const legacy = normalizeWindUnit(localStorage.getItem(LEGACY_WIND_KEY));
        if (legacy) merged.wind = legacy;
      }
      return merged;
    }
    // No unified prefs yet: still honour a standalone legacy wind choice.
    const legacy = normalizeWindUnit(localStorage.getItem(LEGACY_WIND_KEY));
    if (legacy) return { ...DEFAULT_UNITS, wind: legacy };
  } catch {
    /* fall through to defaults */
  }
  return DEFAULT_UNITS;
}

const PrefsCtx = createContext<PrefsValue | null>(null);

/**
 * User display preferences (measurement units). Persisted to localStorage and
 * consumed via the lib/units formatters at every conditions display site, so a
 * change here takes effect everywhere a value is shown. This is the single
 * source of truth; SpotDataScope reads its wind unit from here.
 */
export function PrefsProvider({ children }: { children: ReactNode }) {
  const [units, setUnits] = useState<Units>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify({ units }));
      // Keep the legacy key in sync so any not-yet-migrated reader still agrees.
      localStorage.setItem(LEGACY_WIND_KEY, units.wind === "kn" ? "kts" : units.wind);
    } catch {
      /* private mode / quota — the choice still applies for this session */
    }
  }, [units]);

  const value = useMemo<PrefsValue>(
    () => ({
      units,
      setUnit: (key, val) => setUnits((u) => ({ ...u, [key]: val })),
    }),
    [units]
  );

  return <PrefsCtx.Provider value={value}>{children}</PrefsCtx.Provider>;
}

export function usePrefs(): PrefsValue {
  const v = useContext(PrefsCtx);
  if (!v) throw new Error("usePrefs must be used within <PrefsProvider>.");
  return v;
}

/** Non-throwing variant for code that may render outside the provider (e.g.
 *  SpotDataScope in isolated tests): falls back to the default units. */
export function useOptionalUnits(): Units {
  return useContext(PrefsCtx)?.units ?? DEFAULT_UNITS;
}

/** The full prefs context, or null when rendered outside the provider. Lets
 *  SpotDataScope read + write the shared wind unit while still working in
 *  isolated tests that mount it without <PrefsProvider>. */
export function useOptionalPrefs(): PrefsValue | null {
  return useContext(PrefsCtx);
}
