import { useId, useRef, useState } from "react";
import { InfoIcon } from "../lib/icons";

type AttributionSource = "carto" | "esri";

/**
 * The map's sources, behind a small `i` (2026-10-11): the glyph alone, no
 * button surface, like every other mark on the map — and the panel unfolds to
 * the LEFT of it rather than over the map above, so the bottom edge stays one
 * line and nothing jumps upward when it opens.
 */
export default function LeafletAttributionDisclosure({
  source,
  tone = "light",
  className = "",
}: {
  source: AttributionSource;
  tone?: "light" | "overlay";
  /** Extra class on the outer dock — lets a map move the glyph out of the way
   *  of its own bottom furniture (the wind map's forecast sheet). */
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const overlay = tone === "overlay";

  return (
    <div
      className={`pointer-events-none absolute bottom-2 right-2 z-map-ui flex max-w-[calc(100%-1rem)] items-center gap-1.5 ${className}`}
      onKeyDown={(event) => {
        if (event.key !== "Escape" || !open) return;
        setOpen(false);
        buttonRef.current?.focus();
      }}
    >
      {open && (
        <aside
          id={panelId}
          aria-label="Kartenquellen"
          className={`pointer-events-auto max-w-[280px] rounded-card border px-2.5 py-1.5 text-micro leading-relaxed shadow-card ${
            overlay
              ? "border-white/20 bg-black/85 text-white"
              : "border-line bg-surface/95 text-ink"
          }`}
        >
          {source === "carto" ? (
            <>
              ©{" "}
              <a className="underline underline-offset-2" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
                OpenStreetMap
              </a>{" "}
              ©{" "}
              <a className="underline underline-offset-2" href="https://carto.com/attributions" target="_blank" rel="noreferrer">
                CARTO
              </a>
            </>
          ) : (
            <>
              Tiles ©{" "}
              <a className="underline underline-offset-2" href="https://www.esri.com/" target="_blank" rel="noreferrer">
                Esri
              </a>{" "}
              · Quellen: Esri, Maxar, Earthstar Geographics und die GIS User Community
            </>
          )}
        </aside>
      )}

      <button
        ref={buttonRef}
        type="button"
        aria-label={open ? "Kartenquellen ausblenden" : "Kartenquellen anzeigen"}
        aria-expanded={open}
        aria-controls={panelId}
        title={open ? "Kartenquellen ausblenden" : "Kartenquellen anzeigen"}
        onClick={() => setOpen((current) => !current)}
        className="swd-map-sources-glyph pointer-events-auto grid h-6 w-6 shrink-0 place-items-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <InfoIcon width={14} height={14} />
      </button>
    </div>
  );
}
