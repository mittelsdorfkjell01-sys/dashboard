import { lazy, Suspense, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import MobileSearchTrigger from "./MobileSearchTrigger";
import type { WhereSelection } from "../lib/searchSubmit";

const MobileSearchSheet = lazy(() => import("./MobileSearchSheet"));

/**
 * The public map's search entry: the magnifier glyph alone, sized to sit in
 * the map's own control row, opening the site's one search sheet. No wordmark
 * — the map is a full-bleed tool, not a branded page (2026-08-23 feedback) —
 * and no second search implementation.
 *
 * One surface on every viewport and on both halves of the map (2026-11-16):
 * the spot map used to dock a search PILL at the bottom centre (and a wider
 * SearchBar dropdown on desktop) while the wind map carried this glyph in the
 * top-right corner, so the same map offered two different searches in two
 * different places depending on which mode you were in. The glyph is now the
 * only one, in the corner, on both.
 */
export default function Header({
  whereOnly = false,
  onResolve,
}: {
  /** Place-only search: the sheet drops "Wann?" and "Welche Sportart?". */
  whereOnly?: boolean;
  /** When set, submitting hands the picked place back instead of navigating to
   *  the results page — the map moves its camera to it instead. */
  onResolve?: (selection: WhereSelection | null, text: string) => void;
}) {
  const { t } = useTranslation();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [mobileSearchLoaded, setMobileSearchLoaded] = useState(false);
  const mobileSearchTriggerRef = useRef<HTMLButtonElement | null>(null);
  const openMobileSearch = (trigger: HTMLButtonElement) => {
    mobileSearchTriggerRef.current = trigger;
    setMobileSearchLoaded(true);
    setMobileSearchOpen(true);
  };

  return (
    <>
      <div className="swd-inline-search pointer-events-auto flex items-center">
        <MobileSearchTrigger onClick={openMobileSearch} label={t("header.searchPlaceholder")} iconOnly />
      </div>
      {mobileSearchLoaded && (
        <Suspense fallback={null}>
          <MobileSearchSheet
            open={mobileSearchOpen}
            onClose={() => setMobileSearchOpen(false)}
            returnFocusRef={mobileSearchTriggerRef}
            whereOnly={whereOnly}
            onResolve={onResolve}
          />
        </Suspense>
      )}
    </>
  );
}
