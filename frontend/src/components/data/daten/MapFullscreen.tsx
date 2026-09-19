import { useEffect } from "react";
import { createPortal } from "react-dom";
import type { LiveConditionsRead } from "../../../lib/api";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import type { Spot } from "../../../lib/types";
import SpotMap from "../../SpotMap";
import TimeScrubber from "../TimeScrubber";

/**
 * Mobile fullscreen wind/wave map (Windfinder-style). Opened by tapping the
 * embedded Daten map preview. The map fills the screen and is pannable/zoomable;
 * the layer switch (Wind/Wellen) sits top-left inside the map, and a time
 * scrubber along the bottom drives the shared forecast selection. Rendered
 * through a portal but kept inside the React tree, so it still reads the spot
 * data scope (`useSpotDataScope`) that the scrubber and map depend on. The
 * `daten-dark` class re-scopes the dark instrument palette onto the portal root
 * (which lives outside the page's `.daten-dark` wrapper).
 */
export default function MapFullscreen({
  spot,
  live,
  forecast,
  onClose,
}: {
  spot: Spot;
  live?: LiveConditionsRead | null;
  forecast: NormalizedForecastSeries | null;
  onClose: () => void;
}) {
  // Lock body scroll and wire Escape while the overlay is open.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return createPortal(
    <div
      className="daten-dark fixed inset-0 z-[2000] flex flex-col bg-page"
      role="dialog"
      aria-modal="true"
      aria-label="Windkarte im Vollbild"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-ui font-semibold text-ink">Windkarte</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Vollbild schließen"
          className="grid h-9 w-9 place-items-center rounded-full border border-line text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          <svg width={18} height={18} viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="relative min-h-0 flex-1">
        <SpotMap
          spot={spot}
          live={live}
          forecast={forecast}
          fill
          interactive
          showModeSwitch
          showBadge={false}
          rounded={false}
        />
      </div>

      {/* Time scrubber renders nothing when the spot has no hourly forecast. */}
      <div className="shrink-0 pb-[env(safe-area-inset-bottom)]">
        <TimeScrubber />
      </div>
    </div>,
    document.body,
  );
}
