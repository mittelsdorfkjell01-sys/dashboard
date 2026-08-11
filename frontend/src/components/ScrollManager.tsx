// Keeps normal navigation working under Lenis (System A). Mounted once inside
// the router. On a route change it resets to the top; a `#hash` link animates to
// the target through Lenis (or native scroll under reduced motion). This is the
// single place that owns programmatic scrolling, so there are no competing
// scrollTo calls fighting Lenis.

import { useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { getLenis } from "../lib/lenis";

const scrollPositions = new Map<string, number>();

export default function ScrollManager() {
  const { pathname, hash, key, state } = useLocation();
  const navigationType = useNavigationType();

  useLayoutEffect(() => {
    return () => {
      scrollPositions.set(key, window.scrollY);
    };
  }, [key]);

  useLayoutEffect(() => {
    const lenis = getLenis();

    // Spot-detail tabs are two real routes, but visually they are one page.
    // Their links opt out of the normal route reset so the viewport remains
    // at exactly the height from which the visitor switched tabs.
    if (navigationType !== "POP" && state?.preserveScroll) return;

    if (hash) {
      const el = document.querySelector(hash);
      if (el) {
        if (lenis) lenis.scrollTo(el as HTMLElement, { offset: -80 });
        else (el as HTMLElement).scrollIntoView({ behavior: "smooth" });
        return;
      }
    }

    const target = navigationType === "POP" ? scrollPositions.get(key) ?? 0 : 0;
    if (lenis) lenis.scrollTo(target, { immediate: true });
    else window.scrollTo(0, target);
  }, [pathname, hash, key, navigationType, state]);

  return null;
}
