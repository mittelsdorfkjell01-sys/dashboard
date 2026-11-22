import type { WindDisplayMode } from "./contracts";

/**
 * How the wind is drawn: drifting particles or a lattice of arrows
 * (2026-11-19). It sits directly under the mode words and speaks their
 * language — two words, no pill, no border, no fill, the active one solid —
 * one size smaller, because it refines the mode above it rather than being a
 * sibling of it. Only the wind has it; the waves always draw crests.
 *
 * The styles live in map.css next to `.swd-explorer-mode`, for the same
 * reason: the map's glyph ink, halo and focus ring come from there.
 */
export default function WindDisplayToggle({
  display,
  onChange,
}: {
  display: WindDisplayMode;
  onChange: (display: WindDisplayMode) => void;
}) {
  return (
    <div className="swd-wind-display z-scrim" role="group" aria-label="Darstellung des Winds">
      <button type="button" className="text-caption font-medium aria-pressed:font-semibold" aria-pressed={display === "particles"} onClick={() => onChange("particles")}>
        Partikel
      </button>
      <span className="text-caption" aria-hidden="true">·</span>
      <button type="button" className="text-caption font-medium aria-pressed:font-semibold" aria-pressed={display === "arrows"} onClick={() => onChange("arrows")}>
        Pfeile
      </button>
    </div>
  );
}
