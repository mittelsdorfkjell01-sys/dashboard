import { useCallback, useEffect, useRef, useState } from "react";
import { useOptionalAuth } from "../context/AuthContext";
import { updatePreferences, type MapLocation } from "./account";

const KEY = "swd.mapLocation";

function readLocal(): MapLocation | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<MapLocation>;
    if (typeof value.lat !== "number" || typeof value.lon !== "number") return null;
    if (Math.abs(value.lat) > 90 || Math.abs(value.lon) > 180) return null;
    return { lat: value.lat, lon: value.lon, source: value.source === "gps" ? "gps" : "manual" };
  } catch {
    return null;
  }
}

function writeLocal(location: MapLocation | null): void {
  try {
    if (location) localStorage.setItem(KEY, JSON.stringify(location));
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode / quota: the choice still applies for this visit */
  }
}

const round = (value: number) => Math.round(value * 10_000) / 10_000;

/**
 * "Dein Standort" — the rider's own starting point for the spot map.
 *
 * It is only ever set deliberately (a tap on "Aktuellen Standort verwenden" or
 * "Hier setzen"), never tracked in the background. It lives in this browser
 * and, when signed in, in the account preferences, so a second device starts
 * from the same place. Explicitly removing it removes it in both.
 */
export function useMapLocation() {
  const auth = useOptionalAuth();
  const user = auth?.user ?? null;
  const setUser = auth?.setUser;
  const [location, setLocation] = useState<MapLocation | null>(readLocal);
  const [syncError, setSyncError] = useState(false);
  const hydrated = useRef<string | null>(null);

  useEffect(() => {
    if (!user) { hydrated.current = null; return; }
    if (hydrated.current === user.id) return;
    hydrated.current = user.id;
    const prefs = user.preferences ?? {};
    if ("mapLocation" in prefs) {
      // The account is the source of truth once it has an opinion — including
      // an explicit "removed".
      const remote = prefs.mapLocation ?? null;
      setLocation(remote);
      writeLocal(remote);
      return;
    }
    const local = readLocal();
    if (local) {
      void updatePreferences({ mapLocation: local }).then((updated) => setUser?.(updated)).catch(() => setSyncError(true));
    }
  }, [user, setUser]);

  const save = useCallback((next: MapLocation | null) => {
    const value = next ? { ...next, lat: round(next.lat), lon: round(next.lon) } : null;
    setLocation(value);
    writeLocal(value);
    setSyncError(false);
    if (!user) return;
    void updatePreferences({ mapLocation: value })
      .then((updated) => setUser?.(updated))
      .catch(() => setSyncError(true));
  }, [user, setUser]);

  return { location, save, syncError, signedIn: Boolean(user) };
}
