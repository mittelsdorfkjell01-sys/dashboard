import { useEffect, useState } from "react";

/**
 * Keeps a panel in the DOM long enough to animate both ways with plain CSS
 * transitions (compositor-driven, unlike a JS animation loop).
 *
 * - `mounted` — render the panel while this is true.
 * - `shown`   — put the panel in its open state while this is true. It flips
 *   on two frames after mounting, so the browser paints the closed state first
 *   and the transition actually runs; on close it flips off at once and
 *   `mounted` follows after `exitMs`, when the exit transition has finished.
 *
 * Style the panel from `data-shown={shown}`.
 */
export function usePresence(open: boolean, exitMs: number): { mounted: boolean; shown: boolean } {
  const [mounted, setMounted] = useState(open);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      let inner = 0;
      const outer = requestAnimationFrame(() => {
        inner = requestAnimationFrame(() => setShown(true));
      });
      return () => {
        cancelAnimationFrame(outer);
        if (inner) cancelAnimationFrame(inner);
      };
    }
    setShown(false);
    const timer = window.setTimeout(() => setMounted(false), exitMs);
    return () => window.clearTimeout(timer);
  }, [open, exitMs]);

  return { mounted, shown };
}
