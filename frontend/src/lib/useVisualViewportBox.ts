import { useEffect, useState } from "react";

export type VisualViewportBox = { top: number; height: number };

/**
 * The box a full-screen overlay should fill while the soft keyboard is up.
 *
 * The keyboard does not shrink the layout viewport (iOS Safari, Android
 * Chrome's default), so a plain `fixed inset-0` overlay keeps its full height
 * and whatever sits low in it — a submit button, the last field — ends up
 * behind the keyboard. While `active`, this returns the *visual* viewport's
 * height and its offset when the browser pans the page up under the keyboard;
 * set both as `top` / `height` on the overlay.
 *
 * Returns null while the visual viewport is the full window, so the overlay's
 * own CSS box stays in charge whenever no keyboard is open.
 */
export function useVisualViewportBox(active: boolean): VisualViewportBox | null {
  const [box, setBox] = useState<VisualViewportBox | null>(null);
  useEffect(() => {
    const vv = typeof window === "undefined" ? undefined : window.visualViewport;
    if (!active || !vv) return;
    const update = () => {
      const shrunk = vv.height < window.innerHeight - 1 || vv.offsetTop > 0;
      setBox(shrunk ? { top: vv.offsetTop, height: vv.height } : null);
    };
    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
      setBox(null);
    };
  }, [active]);
  return box;
}

/** True when `box` is small enough that a soft keyboard is the likely cause. */
export function keyboardLikelyOpen(box: VisualViewportBox | null): boolean {
  return box !== null && typeof window !== "undefined" && box.height < window.innerHeight * 0.85;
}
