// Keeps normal navigation working under Lenis (System A). Mounted once inside
// the router. On a route change it resets to the top; a `#hash` link animates to
// the target through Lenis (or native scroll under reduced motion). This is the
// single place that owns programmatic scrolling, so there are no competing
// scrollTo calls fighting Lenis.

import { useLayoutEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { getLenis } from "../lib/lenis";

const scrollPositions = new Map<string, number>();
let pendingSpotTabScroll: number | null = null;

export default function ScrollManager() {
  const { pathname, hash, key, state } = useLocation();
  const navigationType = useNavigationType();
  // The page the last run saw. A change of the query only (a switch that
  // writes its state into the link: Wind/Welle, the Windmonate windows, the
  // results view) is the same page — it keeps its scroll position.
  const lastPathname = useRef(pathname);

  useLayoutEffect(() => {
    return () => {
      scrollPositions.set(key, window.scrollY);
    };
  }, [key]);

  useLayoutEffect(() => {
    const lenis = getLenis();
    const samePage = lastPathname.current === pathname;
    lastPathname.current = pathname;

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
      if (!el) {
        // The target page is a lazily loaded chunk: on a cross-page jump (the
        // burger menu's search lands on a section of a legal page) the anchor
        // is not in the DOM yet. Start at the top and retry for a moment
        // instead of dropping the jump.
        if (lenis) lenis.scrollTo(0, { immediate: true });
        else window.scrollTo(0, 0);
        const timers = [120, 300, 700].map((delay) =>
          window.setTimeout(() => {
            const late = document.querySelector(hash) as HTMLElement | null;
            if (!late || late.dataset.scrolledTo === key) return;
            late.dataset.scrolledTo = key;
            const current = getLenis();
            if (current) {
              current.resize();
              current.scrollTo(late, { offset: -80 });
            } else {
              late.scrollIntoView({ behavior: "smooth" });
            }
          }, delay),
        );
        return () => timers.forEach((timer) => window.clearTimeout(timer));
      }
      if (el) {
        if (lenis) {
          // Re-measure before jumping. Lenis caches the document height, and
          // every route here is a lazily loaded chunk: the page grows after
          // that measurement, so the cached limit is still the one from the
          // loading shell. Lenis clamps the target against it, and the FIRST
          // in-page jump on a freshly opened page silently does nothing —
          // only once something else has scrolled (which refreshes the cache)
          // do the section links start working.
          lenis.resize();
          lenis.scrollTo(el as HTMLElement, { offset: -80 });
        } else {
          (el as HTMLElement).scrollIntoView({ behavior: "smooth" });
        }
        return;
      }
    }

    // Same page, new query: stay where the visitor is (2026-11-25, "die Seite
    // soll nicht neu laden, sondern am gleichen Punkt weitermachen").
    if (samePage && navigationType !== "POP") return;

    const target = navigationType === "POP" ? scrollPositions.get(key) ?? 0 : 0;
    if (lenis) lenis.scrollTo(target, { immediate: true });
    else window.scrollTo(0, target);
  }, [pathname, hash, key, navigationType, state]);

  return null;
}
