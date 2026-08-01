// System B — the page-replacement transition. STRICTLY decoupled from System A
// (Lenis / smooth scroll):
//
//   Lenis scroll position ──► crosses threshold ──► transition.start() ONCE
//                                                        │
//                                                        ▼
//                                          autonomous, time-based timeline
//                                          (framer-motion), ~1.2s, plays fully
//
// Lenis never drives the animation's progress, and the animation never reads
// the scroll position after it has started. The only coupling is the one-way
// threshold that fires `start()` a single time (guarded by a state machine:
// idle → transitioning → completed, with a reset when the user returns to top).
//
// The hero stays 100% static — this overlay only reveals a *new white layer*
// over it via an animated, turbulence-displaced SVG mask (the "liquid/smoke"
// edge). It is always `pointer-events: none`, so it never locks scrolling.
//
// Performance: the reveal is driven by framer-motion motion values (no React
// re-render per frame); only one SVG attribute (the mask circle radius) and one
// opacity are written per frame during the ~1.2s run — nothing during normal
// scrolling.

import { useEffect, useRef } from "react";
import { animate, motion, useMotionValue, useMotionValueEvent } from "framer-motion";
import { prefersReducedMotion, useLenis } from "../lib/lenis";

type Phase = "idle" | "transitioning" | "completed";

export default function LiquidReveal() {
  // reveal: 0 → 1 grows the mask circle; curtain: 1 → 0 fades the layer out at
  // the end so the real (in-flow) white content shows through. Motion values do
  // not trigger React renders.
  const reveal = useMotionValue(0);
  const curtain = useMotionValue(1);
  const circleRef = useRef<SVGCircleElement>(null);
  // The state machine lives in a ref so the scroll handler can guard on it
  // without ever re-rendering React.
  const phase = useRef<Phase>("idle");
  const stopRef = useRef<(() => void) | null>(null);
  const lenis = useLenis();

  // Write the growing radius straight to the SVG attribute (one element, only
  // while animating). 0..1 → 0..160 in the 0..100 viewBox (covers the corners).
  useMotionValueEvent(reveal, "change", (v) => {
    circleRef.current?.setAttribute("r", (v * 160).toFixed(2));
  });

  useEffect(() => {
    // Reduced motion: no autonomous transition at all — the page just scrolls,
    // hero static, white content below. (Lenis is also disabled in that mode.)
    if (prefersReducedMotion()) return;

    const start = () => {
      phase.current = "transitioning";
      const grow = animate(reveal, 1, {
        duration: 0.9,
        ease: [0.22, 1, 0.36, 1], // smooth, decisive open
        onComplete: () => {
          const fade = animate(curtain, 0, {
            duration: 0.35,
            ease: "easeOut",
            onComplete: () => {
              phase.current = "completed";
              stopRef.current = null;
            },
          });
          stopRef.current = () => fade.stop();
        },
      });
      stopRef.current = () => grow.stop();
    };

    const reset = () => {
      phase.current = "idle";
      reveal.set(0);
      curtain.set(1);
    };

    // Threshold = most of the way down the hero, so the reveal lands as the
    // white section takes over. Recomputed per event (cheap) for viewport
    // resizes / mobile URL-bar changes.
    const onScroll = () => {
      const y = window.scrollY; // Lenis drives native scroll, so this is current
      if (phase.current === "idle" && y > window.innerHeight * 0.72) start();
      else if (phase.current === "completed" && y < 8) reset();
    };

    // Subscribe to the ONE Lenis scroll stream (no extra rAF / scroll loop).
    // Re-runs when the Lenis instance becomes available (parent effect mounts
    // after this child's), so we always end up on the real Lenis stream.
    if (lenis) {
      lenis.on("scroll", onScroll);
      return () => {
        lenis.off("scroll", onScroll);
        stopRef.current?.();
      };
    }
    // Fallback before Lenis is ready (Lenis drives native scroll, so window
    // scroll events are still current). Passive + cheap, no rAF loop.
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      stopRef.current?.();
    };
  }, [lenis, reveal, curtain]);

  if (prefersReducedMotion()) return null;

  return (
    <motion.div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-40"
      style={{ opacity: curtain }}
    >
      <svg
        className="h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <defs>
          {/* Turbulent displacement + a touch of blur = organic liquid/smoke edge. */}
          <filter id="liquid-edge" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.018 0.028"
              numOctaves={2}
              seed={7}
              result="noise"
            />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale={9} />
            <feGaussianBlur stdDeviation="0.6" />
          </filter>
          <mask id="liquid-mask">
            <rect x="0" y="0" width="100" height="100" fill="black" />
            <circle
              ref={circleRef}
              cx="50"
              cy="58"
              r="0"
              fill="white"
              filter="url(#liquid-edge)"
            />
          </mask>
        </defs>
        {/* The new white "page" — revealed by the growing, displaced mask. */}
        <rect x="0" y="0" width="100" height="100" fill="#ffffff" mask="url(#liquid-mask)" />
      </svg>
    </motion.div>
  );
}
