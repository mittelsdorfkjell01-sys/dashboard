import type { ExplorerMode } from "./fieldUrlState";

/**
 * The one switch between the public map's two halves, on both of them. It is
 * deliberately not a control surface (2026-10-11): no pill, no border, no
 * fill — two small words at the top edge, the active one solid and the other
 * quiet, so it weighs the same as the bare glyphs in the corners.
 */
export default function ExplorerModeToggle({ mode, onChange }: { mode: ExplorerMode; onChange: (mode: ExplorerMode) => void }) {
  return (
    <div className="swd-explorer-mode" role="group" aria-label="Kartenmodus">
      <button type="button" aria-pressed={mode === "spots"} onClick={() => onChange("spots")}>Spots</button>
      <span aria-hidden="true">·</span>
      <button type="button" aria-pressed={mode === "wind"} onClick={() => onChange("wind")}>Wind</button>
      <span aria-hidden="true">·</span>
      <button type="button" aria-pressed={mode === "waves"} onClick={() => onChange("waves")}>Wellen</button>
    </div>
  );
}
