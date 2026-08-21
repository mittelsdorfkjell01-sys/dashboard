import { useEffect, useRef, useState } from "react";

/**
 * Hides once the user scrolls down past a small threshold, reappears the
 * moment they scroll up — the familiar mobile-browser-chrome pattern. Always
 * visible near the very top of the page.
 */
export function useAutoHideHeader(revealThreshold = 8) {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);

  useEffect(() => {
    lastY.current = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      const delta = y - lastY.current;
      if (y <= 4) setHidden(false);
      else if (delta > revealThreshold) setHidden(true);
      else if (delta < -revealThreshold) setHidden(false);
      lastY.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [revealThreshold]);

  return hidden;
}
