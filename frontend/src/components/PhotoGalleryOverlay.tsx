import type { RefObject } from "react";
import { resolveMediaUrl, type CommunityImage } from "../lib/api";
import OverlayPanel from "./OverlayPanel";

/** Fotogalerie overlay (Figma Frame_10) — title left, subtitle right, an
 *  asymmetric photo grid below. Triggered only by the gallery tile's
 *  "Fotogalerie" pill (see `SpotGalleryTile`). */
export default function PhotoGalleryOverlay({
  open,
  onClose,
  triggerRef,
  photos,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  photos: CommunityImage[];
}) {
  return (
    <OverlayPanel open={open} onClose={onClose} triggerRef={triggerRef}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-editorial-2 font-semibold text-ink">Fotogalerie</h2>
        <p className="text-body text-muted">Die besten Momente vom Spot</p>
      </div>

      {photos.length === 0 ? (
        <p className="mt-8 text-body text-muted">Noch keine Fotos von hier.</p>
      ) : (
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3">
          {photos.map((p, i) => (
            <div
              key={p.id}
              className={`overflow-hidden rounded-2xl bg-band ${
                i % 5 === 3 ? "col-span-2 aspect-[2/1]" : "aspect-square"
              }`}
            >
              <img
                src={resolveMediaUrl(p.url)}
                alt={p.credit ?? ""}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            </div>
          ))}
        </div>
      )}
    </OverlayPanel>
  );
}
