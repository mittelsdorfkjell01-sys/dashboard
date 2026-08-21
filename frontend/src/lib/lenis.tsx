// The website's single smooth-scroll layer (System A).
//
// One Lenis instance, one requestAnimationFrame loop, provided to the tree via
// context and exposed as a module singleton (`getLenis`) for non-React callers
// (ScrollManager, the page-replacement trigger). Lenis only ever smooths the
// main window scroll; inner scrollables (Leaflet maps, modals, overflow panels)
// opt out with `data-lenis-prevent` so their native wheel/touch keeps working.
//
// This layer is deliberately independent of the page-replacement transition
// (System B): it never reads or drives that animation's progress. The only link
// is a scroll threshold the transition itself watches (see usePageReplacement).

import Lenis from "lenis";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// Module singleton so non-React code (route scroll reset, transition trigger)
// can reach the one instance without prop-drilling or context.
let _lenis: Lenis | null = null;
export const getLenis = (): Lenis | null => _lenis;

const LenisContext = createContext<Lenis | null>(null);
export const useLenis = (): Lenis | null => useContext(LenisContext);

export const prefersReducedMotion = (): boolean =>
  typeof window !== "undefined" &&
  !!window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function LenisProvider({ children }: { children: ReactNode }) {
  const [lenis, setLenis] = useState<Lenis | null>(null);

  useEffect(() => {
    // Reduced motion: no smoothing at all — the browser's native scroll stays
    // fully in charge (System B is skipped separately). Navigation/anchors work
    // via the ScrollManager's native fallback.
    const nativeTouch = window.matchMedia("(pointer: coarse) and (hover: none)").matches;
    if (prefersReducedMotion() || nativeTouch) return;

    const instance = new Lenis({
      duration: 1.1, // calm, high-end momentum (not floaty, not abrupt)
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // expo-out
      smoothWheel: true, // desktop wheel/trackpad smoothing
      // Touch: keep the OS's native momentum. syncTouch on iOS/Android tends to
      // feel laggy and fights the rubber-band, so we leave touch native.
      syncTouch: false,
      touchMultiplier: 1.1,
      wheelMultiplier: 1,
    });
    _lenis = instance;
    setLenis(instance);

    // The single rAF loop that drives Lenis. Nothing else in the app runs its
    // own scroll rAF loop — subscribers use `lenis.on("scroll", …)` instead.
    let raf = 0;
    const loop = (time: number) => {
      instance.raf(time);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      instance.destroy();
      if (_lenis === instance) _lenis = null;
      setLenis(null);
    };
  }, []);

  return <LenisContext.Provider value={lenis}>{children}</LenisContext.Provider>;
}
