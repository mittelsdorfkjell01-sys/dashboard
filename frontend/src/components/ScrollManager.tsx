// Keeps normal navigation working under Lenis (System A). Mounted once inside
// the router. On a route change it resets to the top; a `#hash` link animates to
// the target through Lenis (or native scroll under reduced motion). This is the
// single place that owns programmatic scrolling, so there are no competing
// scrollTo calls fighting Lenis.

import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { getLenis } from "../lib/lenis";

export default function ScrollManager() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    const lenis = getLenis();

    if (hash) {
      const el = document.querySelector(hash);
      if (el) {
        if (lenis) lenis.scrollTo(el as HTMLElement, { offset: -80 });
        else (el as HTMLElement).scrollIntoView({ behavior: "smooth" });
        return;
      }
    }

    // New route → jump to the top instantly (no animated scroll between pages).
    if (lenis) lenis.scrollTo(0, { immediate: true });
    else window.scrollTo(0, 0);
  }, [pathname, hash]);

  return null;
}
