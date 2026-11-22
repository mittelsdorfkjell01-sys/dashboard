import type { ExplorerMode } from "./fieldUrlState";

/**
 * The one switch between the public map's three halves, on all of them. It is
 * deliberately not a control surface (2026-10-11): no pill, no border, no
 * fill — three small words at the top edge, the active one solid and the
 * others quiet, so it weighs the same as the bare glyphs in the corners.
 *
 * Since 2026-11-16 the words are set at the site's `ui` size and each one
 * carries the 44px touch target the rest of the site uses; they were 12px in
 * a 28px box, which is the smallest primary navigation on the whole product.
 * The look did not change — the hit area did.
 */
export default function ExplorerModeToggle({ mode, onChange }: { mode: ExplorerMode; onChange: (mode: ExplorerMode) => void }) {
  return (
    <div className="swd-explorer-mode z-scrim" role="group" aria-label="Kartenmodus">
      <button type="button" className="text-ui font-medium aria-pressed:font-semibold" aria-pressed={mode === "spots"} onClick={() => onChange("spots")}>Spots</button>
      <span className="text-ui" aria-hidden="true">·</span>
      <button type="button" className="text-ui font-medium aria-pressed:font-semibold" aria-pressed={mode === "wind"} onClick={() => onChange("wind")}>Wind</button>
      <span className="text-ui" aria-hidden="true">·</span>
      <button type="button" className="text-ui font-medium aria-pressed:font-semibold" aria-pressed={mode === "waves"} onClick={() => onChange("waves")}>Wellen</button>
    </div>
  );
}
