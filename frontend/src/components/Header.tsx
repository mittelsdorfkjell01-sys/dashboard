import { lazy, Suspense, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import MobileSearchTrigger from "./MobileSearchTrigger";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import type { WhereSelection } from "../lib/searchSubmit";

const SearchBar = lazy(() => import("./SearchBar"));
const MobileSearchSheet = lazy(() => import("./MobileSearchSheet"));

/**
 * The /map page's own top bar: just the centred search — the same search
 * entry used everywhere else, no second search implementation. No wordmark
 * here (2026-08-23 feedback: the map is a full-bleed tool, not a branded
 * page). The back control lives with the other floating map controls (see
 * MapView's `.swd-map-controls-left`), not in this bar.
 *
 *  - variant "map": the spot map — docked just above the sources button.
 *  - variant "inline": no bar of its own — just the magnifier glyph, sized to
 *    sit inside someone else's control row (the wind map's top bar). One
 *    surface on every viewport: the glyph opens the search sheet, so the map
 *    never grows a second, wider search bar on desktop.
 */
export default function Header({
  variant = "map",
  whereOnly = false,
  onResolve,
}: {
  variant?: "map" | "inline";
  /** Place-only search: the sheet/bar drops "Wann?" and "Welche Sportart?". */
  whereOnly?: boolean;
  /** When set, submitting hands the picked place back instead of navigating to
   *  the results page — the wind map zooms to it instead. */
  onResolve?: (selection: WhereSelection | null, text: string) => void;
}) {
  const { t } = useTranslation();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [mobileSearchLoaded, setMobileSearchLoaded] = useState(false);
  const mobileSearchTriggerRef = useRef<HTMLButtonElement | null>(null);
  const desktop = useDesktopViewport();
  const openMobileSearch = (trigger: HTMLButtonElement) => {
    mobileSearchTriggerRef.current = trigger;
    setMobileSearchLoaded(true);
    setMobileSearchOpen(true);
  };

  const sheet = mobileSearchLoaded && (
    <Suspense fallback={null}>
      <MobileSearchSheet
        open={mobileSearchOpen}
        onClose={() => setMobileSearchOpen(false)}
        returnFocusRef={mobileSearchTriggerRef}
        whereOnly={whereOnly}
        onResolve={onResolve}
      />
    </Suspense>
  );

  if (variant === "inline") {
    return (
      <>
        <div className="swd-inline-search pointer-events-auto flex items-center">
          <MobileSearchTrigger onClick={openMobileSearch} label={t("header.searchPlaceholder")} iconOnly />
        </div>
        {sheet}
      </>
    );
  }

  return (
    <>
      {/* Docked at the bottom of the map, centred, a little above the
          map-sources info button (LeafletAttributionDisclosure, pinned
          bottom-right). The Spots/Wind mode toggle keeps the very top (see
          MapView's `.swd-explorer-mode`). MapView hides this bar whenever a
          bottom dock — the selected-spot chart or the spot row — occupies the
          same space. */}
      <header className="pointer-events-none absolute inset-x-0 bottom-0 z-header">
        <div
          className="mx-auto max-w-page px-4 pb-[calc(64px+env(safe-area-inset-bottom))]"
        >
          <div className="relative flex min-h-[44px] items-center justify-center sm:min-h-[48px]">
            <div className="pointer-events-auto flex items-center">
              {/* A small centred pill — the compact landing-search size, not a
                  full-width bar; capped to the viewport on the narrowest phones. */}
              <div className="w-[min(260px,calc(100vw-32px))] sm:hidden">
                <MobileSearchTrigger onClick={openMobileSearch} label={t("header.searchPlaceholder")} compact />
              </div>
              <div className="hidden sm:block">
                {desktop && (
                  <Suspense fallback={<div aria-hidden className="h-11 w-48 rounded-card bg-surface shadow-card" />}>
                    <SearchBar variant="pill" whereOnly={whereOnly} onResolve={onResolve} />
                  </Suspense>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>
      {sheet}
    </>
  );
}
