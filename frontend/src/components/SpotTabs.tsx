import { useRef, type KeyboardEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import type { LiveConditionsRead } from "../lib/api";
import { degToCompass } from "./WindRose";
import WindArrow from "./WindArrow";

export interface SpotTab {
  id: string;
  label: string;
  href: string;
}

/**
 * Real-route tabs (Info / Daten) — replaces SpotSubnav's jump-link nav, which
 * competed with these as a second navigation system. Sticky at the viewport
 * top, taking over once LandingHeader (an overlay confined to the hero)
 * scrolls out of view. The live wind stays visible here regardless of which
 * tab is active, so switching tabs is never required just to check it.
 *
 * The tabs sit in their own centered column (a spacer on the left balances
 * the live-wind column on the right, so the pair stays truly centered
 * whether or not `live` is showing). The active tab is marked two ways: a
 * teal underline that slides between tabs via a shared `layoutId` (spring,
 * no bounce), and the label itself stepping from `ink-soft`/regular to
 * `ink`/medium — an invisible medium-weight copy of the label is rendered
 * underneath to reserve its width, so that weight step never shifts layout.
 */
export default function SpotTabs({ tabs, live }: { tabs: SpotTab[]; live: LiveConditionsRead | null }) {
  const { pathname } = useLocation();
  const activeIndex = Math.max(
    0,
    tabs.findIndex((t) => t.href === pathname)
  );
  const tabRefs = useRef<(HTMLAnchorElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent<HTMLAnchorElement>, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = e.key === "ArrowRight" ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
    tabRefs.current[next]?.focus();
  };

  const wind = live?.current.wind;
  const dir = live?.current.dir;

  return (
    <div className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur-xl">
      <div className="mx-auto grid max-w-[1180px] grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 py-2 sm:px-8">
        <div aria-hidden="true" />

        <div role="tablist" aria-label="Spot-Ansicht" className="flex justify-self-center">
          {tabs.map((tab, i) => {
            const active = i === activeIndex;
            return (
              <Link
                key={tab.id}
                ref={(el) => (tabRefs.current[i] = el)}
                id={`tab-${tab.id}`}
                role="tab"
                aria-selected={active}
                tabIndex={active ? 0 : -1}
                to={tab.href}
                onKeyDown={(e) => onKeyDown(e, i)}
                className="relative flex h-12 min-w-[140px] items-center justify-center px-4 text-label"
              >
                <span className="relative grid">
                  <span aria-hidden="true" className="invisible col-start-1 row-start-1 font-medium">
                    {tab.label}
                  </span>
                  <span
                    className={`col-start-1 row-start-1 text-center transition-colors duration-200 ${
                      active ? "font-medium text-ink" : "font-normal text-ink-soft"
                    }`}
                  >
                    {tab.label}
                  </span>
                </span>
                {active && (
                  <motion.span
                    layoutId="spot-tab-indicator"
                    className="absolute inset-x-3 bottom-1.5 h-[3px] rounded-full bg-teal"
                    transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  />
                )}
              </Link>
            );
          })}
        </div>

        <div className="flex justify-self-end">
          {typeof wind === "number" && (
            <div className="flex shrink-0 items-center gap-1.5 text-ui font-medium text-ink">
              <span aria-hidden="true" className="inline-block h-1.5 w-1.5 rounded-full bg-orange" />
              <WindArrow dir={dir ?? 0} size={16} className="text-ink-soft" />
              {Math.round(wind)} kts
              {typeof dir === "number" && <span className="text-caption text-muted">{degToCompass(dir)}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
