import type { PublicMapMode } from "../lib/publicMap";

/** Wind / Wellen / Brandung focus-mode switch for the public map. Brandung
 *  has no backend layer yet (no validated nearshore engine — see
 *  docs/map-redesign-backend-gaps.md), so it stays visible but permanently
 *  disabled with a concrete reason, rather than hidden or silently omitted. */
export default function MapModeSwitch({ mode, onChange }: { mode: PublicMapMode; onChange: (mode: PublicMapMode) => void }) {
  return (
    <div className="swd-map-mode-switch" role="group" aria-label="Kartenmodus">
      <button
        type="button"
        className="swd-map-mode-pill"
        aria-pressed={mode === "wind"}
        onClick={() => onChange("wind")}
      >
        Wind
      </button>
      <button
        type="button"
        className="swd-map-mode-pill"
        aria-pressed={mode === "waves"}
        onClick={() => onChange("waves")}
      >
        Wellen
      </button>
      <button
        type="button"
        className="swd-map-mode-pill"
        disabled
        aria-disabled="true"
        title="Kein validiertes Nearshore-Modell verfügbar"
      >
        Brandung
      </button>
    </div>
  );
}
