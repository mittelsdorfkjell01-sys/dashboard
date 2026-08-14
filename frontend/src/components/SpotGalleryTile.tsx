import { useState, type RefObject } from "react";
import { resolveMediaUrl, type CommunityImage } from "../lib/api";
import { ChevronLeftIcon, ChevronRightIcon } from "../lib/icons";

/**
 * The Info tab's portrait gallery tile (Figma Frame_9). A single big image
 * with its own prev/next arrows to page through the spot's photos in place.
 * The image surface opens the full gallery overlay (Frame_10). Landscape photos are center-cropped to
 * hold the portrait frame rather than letterboxed or stretched.
 */
export default function SpotGalleryTile({
  photos,
  onOpenGallery,
  galleryTriggerRef,
}: {
  photos: CommunityImage[];
  onOpenGallery: () => void;
  /** So the overlay can return focus here on close. */
  galleryTriggerRef?: RefObject<HTMLButtonElement>;
}) {
  const [index, setIndex] = useState(0);
  const photo = photos[index];
  const go = (delta: number) => setIndex((i) => (i + delta + photos.length) % photos.length);

  return (
    <div className="spot-media-frame relative aspect-[3/4] overflow-hidden bg-band sm:aspect-[4/3] lg:aspect-auto">
      {photo && (
        <img
          key={photo.id}
          src={resolveMediaUrl(photo.url)}
          alt={photo.credit ?? ""}
          className="h-full w-full object-cover object-center"
          loading="lazy"
        />
      )}

      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/65 via-black/5 to-transparent" />

      <button ref={galleryTriggerRef} type="button" onClick={onOpenGallery} aria-label="Fotogalerie öffnen" className="absolute inset-0 z-[5] cursor-zoom-in [-webkit-tap-highlight-color:transparent]" />

      {photos.length > 1 && (
        <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
          <button
            type="button"
            onClick={() => go(-1)}
            aria-label="Vorheriges Bild"
            className="grid h-11 w-11 place-items-center rounded-2xl bg-teal/80 text-white transition-colors hover:bg-teal sm:h-9 sm:w-9"
          >
            <ChevronLeftIcon width={18} height={18} />
          </button>
          <button
            type="button"
            onClick={() => go(1)}
            aria-label="Nächstes Bild"
            className="grid h-11 w-11 place-items-center rounded-2xl bg-teal/80 text-white transition-colors hover:bg-teal sm:h-9 sm:w-9"
          >
            <ChevronRightIcon width={18} height={18} />
          </button>
        </div>
      )}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-5 text-white">
        <p className="text-title font-semibold text-balance">Community-Galerie</p>
        <p className="mt-1 text-body text-white/85">Füge deine Bilder hinzu</p>
      </div>
    </div>
  );
}
