import { useLayoutEffect, useRef, type RefObject } from "react";

const LEAD = "var(--sw-dur-base) var(--sw-ease)";
const TRAIL = "var(--sw-dur-base) var(--sw-ease) 70ms";

/**
 * Drives the active-segment surface of a segmented control (chosen
 * 2026-11-24, "Fläche dehnt sich"): instead of jumping, the surface stretches
 * toward the newly pressed segment — the leading edge moves first, the
 * trailing edge follows 70ms later — so the eye travels with it.
 *
 * The indicator is one absolutely positioned element inside the tray (the
 * tray must be `position: relative`); it is placed with `left` / `right` in
 * px, measured from the pressed button (`[aria-pressed="true"]`). First
 * placement, resizes and reduced motion jump without a transition.
 */
export function useStretchIndicator(
  trayRef: RefObject<HTMLElement>,
  indicatorRef: RefObject<HTMLElement>,
  activeKey: string,
): void {
  const last = useRef<{ left: number; right: number } | null>(null);

  useLayoutEffect(() => {
    const tray = trayRef.current;
    const indicator = indicatorRef.current;
    if (!tray || !indicator) return;

    const place = (animate: boolean) => {
      const button = tray.querySelector<HTMLElement>('[aria-pressed="true"]');
      if (!button) {
        indicator.style.opacity = "0";
        return;
      }
      const left = button.offsetLeft;
      // `right` is measured from the tray's visible (padding-box) edge, also
      // when the tray scrolls sideways — not from the end of its content.
      const right = tray.clientWidth - (left + button.offsetWidth);
      const previous = last.current;
      if (previous && previous.left === left && previous.right === right) return;
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      if (!animate || !previous || reduce) {
        indicator.style.transition = "none";
      } else if (left > previous.left) {
        indicator.style.transition = `right ${LEAD}, left ${TRAIL}`;
      } else {
        indicator.style.transition = `left ${LEAD}, right ${TRAIL}`;
      }
      indicator.style.left = `${left}px`;
      indicator.style.right = `${right}px`;
      indicator.style.opacity = "1";
      last.current = { left, right };
    };

    place(true);
    // Late layout changes (web font arriving, viewport resize) re-place the
    // surface without animating. Identical measurements are skipped, so this
    // never cuts short the stretch that `place(true)` just started.
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => place(false));
    observer.observe(tray);
    Array.from(tray.children).forEach((child) => observer.observe(child));
    return () => observer.disconnect();
  }, [trayRef, indicatorRef, activeKey]);
}
