import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** What the Daten tab is laid out for (2026-11-25): the wind (default) or the
 *  sea — wave rows on top, wind below. */
export type DatenFocus = "wind" | "wave";

const STORAGE_KEY = "sw-daten-focus";

function stored(): DatenFocus | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "wave" || value === "wind" ? value : null;
  } catch {
    return null;
  }
}

/**
 * The focus lives in the link (`?fokus=welle`), so a wave view can be
 * shared, and is remembered for the next spot: a surfer who reads waves
 * should not switch on every page.
 */
export function useDatenFocus(): [DatenFocus, (next: DatenFocus) => void] {
  const [params, setParams] = useSearchParams();
  const fromUrl = params.get("fokus");
  const [fallback, setFallback] = useState<DatenFocus>(() => stored() ?? "wind");
  const focus: DatenFocus = fromUrl === "welle" ? "wave" : fromUrl === "wind" ? "wind" : fallback;

  const setFocus = useCallback((next: DatenFocus) => {
    setFallback(next);
    try { window.localStorage.setItem(STORAGE_KEY, next); } catch { /* private mode: the link still carries it */ }
    setParams((current) => {
      const copy = new URLSearchParams(current);
      if (next === "wave") copy.set("fokus", "welle"); else copy.delete("fokus");
      return copy;
    }, { replace: true, preventScrollReset: true });
  }, [setParams]);

  return [focus, setFocus];
}
