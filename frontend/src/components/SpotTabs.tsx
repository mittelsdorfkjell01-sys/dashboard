import { useRef, type KeyboardEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";

export interface SpotTab {
  id: string;
  label: string;
  href: string;
}

/**
 * Real-route tabs (Info / Daten) — replaces SpotSubnav's jump-link nav, which
 * competed with these as a second navigation system. Sits in normal document
 * flow right under the identity card, not pinned to the viewport — it
 * scrolls away with the rest of the page like any other section. Live wind
 * already lives in the identity card above, so it isn't repeated here.
 *
 * The active tab is marked two ways: a teal underline that slides between
 * tabs via a shared `layoutId` (spring, no bounce), and the label itself
 * stepping from `ink-soft`/regular to `ink`/medium — an invisible
 * medium-weight copy of the label is rendered underneath to reserve its
 * width, so that weight step never shifts layout.
 */
export default function SpotTabs({ tabs }: { tabs: SpotTab[] }) {
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

  return (
    <div className="border-b border-line bg-white">
      <div
        role="tablist"
        aria-label="Spot-Ansicht"
        className="mx-auto flex max-w-[1180px] justify-center px-4 sm:px-8"
      >
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
    </div>
  );
}
