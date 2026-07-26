import { useState, type RefObject } from "react";
import { resolveMediaUrl, type CommunityImage } from "../lib/api";
import { ChevronLeftIcon, ChevronRightIcon } from "../lib/icons";

/**
 * The Info tab's portrait gallery tile (Figma Frame_9). A single big image
 * with its own prev/next arrows to page through the spot's photos in place —
 * separate from the "Fotogalerie" pill, which is the *only* trigger for the
 * full gallery overlay (Frame_10). Landscape photos are center-cropped to
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
    <div className="relative aspect-[2/3] overflow-hidden rounded-3xl bg-band">
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

      <button
        ref={galleryTriggerRef}
        type="button"
        onClick={onOpenGallery}
        className="absolute left-4 top-4 z-10 rounded-full bg-teal/50 px-4 py-2 text-label font-medium text-white transition-colors hover:bg-teal/70"
      >
        Fotogalerie
      </button>

      {photos.length > 1 && (
        <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
          <button
            type="button"
            onClick={() => go(-1)}
            aria-label="Vorheriges Bild"
            className="grid h-9 w-9 place-items-center rounded-full bg-teal/50 text-white transition-colors hover:bg-teal/70"
          >
            <ChevronLeftIcon width={18} height={18} />
          </button>
          <button
            type="button"
            onClick={() => go(1)}
            aria-label="Nächstes Bild"
            className="grid h-9 w-9 place-items-center rounded-full bg-teal/50 text-white transition-colors hover:bg-teal/70"
          >
            <ChevronRightIcon width={18} height={18} />
          </button>
        </div>
      )}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-5 text-white">
        <p className="text-title font-semibold text-balance">Community Galerie</p>
        <p className="mt-1 text-body text-white/85">Feel free to add your Images</p>
      </div>
    </div>
  );
}
