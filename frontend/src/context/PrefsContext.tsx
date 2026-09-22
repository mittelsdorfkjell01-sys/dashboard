import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { DEFAULT_UNITS, normalizeWindUnit, type Units } from "../lib/units";
import { useAuth } from "./AuthContext";
import { updatePreferences } from "../lib/account";

interface PrefsValue {
  units: Units;
  setUnit: <K extends keyof Units>(key: K, value: Units[K]) => void;
  retrySave: () => void;
  saving: boolean;
  error: string | null;
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
  const { user, setUser } = useAuth();
  const [units, setUnits] = useState<Units>(load);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hydratedUser = useRef<string | null>(null);
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve());
  const pendingSaves = useRef(0);
  const saveVersion = useRef(0);
  const activeUserId = useRef(user?.id);
  activeUserId.current = user?.id;

  useEffect(() => {
    if (!user) { hydratedUser.current = null; return; }
    if (hydratedUser.current === user.id) return;
    hydratedUser.current = user.id;
    if (user.preferences.units) {
      setUnits(user.preferences.units);
    } else {
      void updatePreferences({ units }).then(setUser).catch(() => {
        setError("Einheiten konnten nicht mit deinem Konto synchronisiert werden.");
      });
    }
  }, [user, setUser, units]);

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
    () => {
      const saveUnits = (next: Units) => {
        if (!user) return;
        const accountId = user.id;
        const version = ++saveVersion.current;
        pendingSaves.current += 1;
        setSaving(true);
        setError(null);
        const save = saveQueue.current.then(() => updatePreferences({ units: next }));
        saveQueue.current = save.then(() => undefined, () => undefined);
        void save.then((updated) => {
          if (activeUserId.current === accountId) {
            setUser(updated);
            if (version === saveVersion.current) setError(null);
          }
        }).catch(() => {
          if (activeUserId.current === accountId && version === saveVersion.current) {
            setError("Einheiten konnten nicht gespeichert werden. Versuche es erneut.");
          }
        }).finally(() => {
          pendingSaves.current -= 1;
          setSaving(pendingSaves.current > 0);
        });
      };
      return {
        units,
        saving,
        error,
        retrySave: () => saveUnits(units),
        setUnit: (key, val) => {
          const next = { ...units, [key]: val };
          setUnits(next);
          setError(null);
          saveUnits(next);
        },
      };
    },
    [units, user, setUser, saving, error]
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
