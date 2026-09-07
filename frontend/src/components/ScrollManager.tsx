// Keeps normal navigation working under Lenis (System A). Mounted once inside
// the router. On a route change it resets to the top; a `#hash` link animates to
// the target through Lenis (or native scroll under reduced motion). This is the
// single place that owns programmatic scrolling, so there are no competing
// scrollTo calls fighting Lenis.

import { useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { getLenis } from "../lib/lenis";

const scrollPositions = new Map<string, number>();
let pendingSpotTabScroll: number | null = null;

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
    // Keep the target across canonical replace navigations and repeat the
    // restoration while the destination swaps its loading shell for content.
    const startsSpotTabNavigation = typeof state?.preserveScroll === "number";
    if (startsSpotTabNavigation) {
      pendingSpotTabScroll = state.preserveScroll;
    }
    if (pendingSpotTabScroll !== null && pathname.startsWith("/spot/")) {
      const target = pendingSpotTabScroll;
      const timers: number[] = [];
      const restore = () => {
        if (document.documentElement.scrollHeight - window.innerHeight < target) return;
        if (lenis) {
          lenis.resize();
          lenis.scrollTo(target, { immediate: true, force: true });
        } else {
          window.scrollTo(0, target);
        }
      };

      restore();
      timers.push(window.setTimeout(restore, 100));
      timers.push(window.setTimeout(() => {
        restore();
        // The spot loader performs a canonical replace after the initial tab
        // push. Keep the value through the push and consume it on that replace.
        if (!startsSpotTabNavigation) pendingSpotTabScroll = null;
      }, 300));
      return () => timers.forEach((timer) => window.clearTimeout(timer));
    }

    if (!pathname.startsWith("/spot/")) pendingSpotTabScroll = null;

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
