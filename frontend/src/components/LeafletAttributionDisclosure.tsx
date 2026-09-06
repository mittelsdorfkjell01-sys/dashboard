import { useId, useRef, useState } from "react";
import { InfoIcon } from "../lib/icons";

type AttributionSource = "carto" | "esri";

export default function LeafletAttributionDisclosure({
  source,
  tone = "light",
}: {
  source: AttributionSource;
  tone?: "light" | "overlay";
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const overlay = tone === "overlay";

  return (
    <div
      className="pointer-events-none absolute bottom-2 right-2 z-[600] flex max-w-[calc(100%-1rem)] flex-col items-end gap-2"
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
          className={`pointer-events-auto max-w-[280px] rounded-lg border px-3 py-2 text-caption leading-relaxed shadow-card ${
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
        className={`pointer-events-auto grid h-11 w-11 place-items-center rounded-full border shadow-card transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
          overlay
            ? "border-white/25 bg-black/75 text-white hover:bg-black/90"
            : "border-line bg-surface/95 text-ink hover:bg-band"
        }`}
      >
        <InfoIcon width={19} height={19} />
      </button>
    </div>
  );
}
