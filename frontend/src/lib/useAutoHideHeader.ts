import { useEffect, useRef, useState } from "react";

const DESKTOP_QUERY = "(min-width: 640px)";

/** Tracks the same breakpoint used by Tailwind's `sm` utilities. It lets
 * code-split desktop controls stay completely out of mobile's JS path. */
export function useDesktopViewport(): boolean {
  const [desktop, setDesktop] = useState(() =>
    typeof window !== "undefined" && window.matchMedia(DESKTOP_QUERY).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(DESKTOP_QUERY);
    const update = () => setDesktop(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return desktop;
}

/**
 * Hides once the user scrolls down past a small threshold, reappears the
 * moment they scroll up — the familiar mobile-browser-chrome pattern. Always
 * visible near the very top of the page.
 */
export function useAutoHideHeader(revealThreshold = 8) {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const accumulated = useRef(0);
  const frame = useRef(0);

  useEffect(() => {
    lastY.current = window.scrollY;
    const update = () => {
      frame.current = 0;
      const y = window.scrollY;
      const delta = y - lastY.current;

      if (Math.sign(delta) !== Math.sign(accumulated.current)) accumulated.current = delta;
      else accumulated.current += delta;

      if (y <= 4) {
        accumulated.current = 0;
        setHidden(false);
      } else if (accumulated.current > revealThreshold) {
        accumulated.current = 0;
        setHidden(true);
      } else if (accumulated.current < -revealThreshold) {
        accumulated.current = 0;
        setHidden(false);
      }
      lastY.current = y;
    };
    const onScroll = () => {
      if (!frame.current) frame.current = window.requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame.current) window.cancelAnimationFrame(frame.current);
    };
  }, [revealThreshold]);

  return hidden;
}
