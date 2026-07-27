import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { resolveMediaUrl, type CommunityImage } from "../lib/api";
import { justifyRows } from "../lib/justifyRows";
import { CloseIcon, ChevronLeftIcon, ChevronRightIcon, PlusIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import { GalleryUploadForm } from "./SpotCommunity";
import CommentAuthChoiceDialog from "./CommentAuthChoiceDialog";
import OverlayPanel from "./OverlayPanel";

/**
 * Fotogalerie overlay (Figma Frame_10) — title left, subtitle right, and the
 * spot's community photos below. The Figma's fixed placeholder grid is
 * replaced by a data-driven **justified layout** (equal-height rows, widths by
 * aspect ratio) so any number of real photos in any format lay out cleanly
 * without hard cropping. Clicking a photo opens a lightbox. With no photos yet
 * it shows an inviting empty state instead of blank tiles.
 *
 * Triggered only by the gallery tile's "Fotogalerie" pill (see SpotGalleryTile).
 */
export default function PhotoGalleryOverlay({
  open,
  onClose,
  triggerRef,
  photos,
  spotId,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  photos: CommunityImage[];
  /** Spot id the upload posts to (same id the photos are read from). */
  spotId?: string;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);

  // Reset transient sub-states whenever the whole overlay closes, so nothing
  // reopens mid-flow on the next open.
  useEffect(() => {
    if (!open) {
      setLightbox(null);
      setUploadOpen(false);
      setAuthOpen(false);
    }
  }, [open]);

  const onAdd = () => {
    // Signed out → offer the same choice as comments: upload anonymously or
    // sign in. Signed in → straight to the upload form.
    if (!user) {
      setAuthOpen(true);
      return;
    }
    setUploadOpen(true);
  };

  return (
    <>
      <OverlayPanel open={open} onClose={onClose} triggerRef={triggerRef}>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-editorial-2 font-semibold text-ink">Fotogalerie</h2>
          <p className="text-body text-muted">Die besten Momente vom Spot</p>
        </div>

        {uploadOpen && spotId && (
          <div className="mt-6">
            <GalleryUploadForm
              spotId={spotId}
              onCancel={() => setUploadOpen(false)}
              onDone={() => setUploadOpen(false)}
            />
          </div>
        )}

        {photos.length === 0 ? (
          <GalleryEmptyState onAdd={onAdd} />
        ) : (
          <JustifiedGallery photos={photos} onOpen={setLightbox} />
        )}

        {/* Round "+" upload FAB, bottom-right of the panel. Hidden while the
            form is open (the form has its own close) and while a photo is
            being viewed full-screen. */}
        {!uploadOpen && lightbox === null && (
          <button
            type="button"
            onClick={onAdd}
            aria-label="Foto hinzufügen"
            className="fixed bottom-6 right-6 z-[1102] grid h-14 w-14 place-items-center rounded-full bg-teal text-white shadow-lg transition-colors hover:bg-teal-hover sm:bottom-8 sm:right-8"
          >
            <PlusIcon className="text-[26px]" />
          </button>
        )}
      </OverlayPanel>

      <CommentAuthChoiceDialog
        open={authOpen}
        title="Foto hochladen"
        anonymousText="dein Foto wird ohne Namen veröffentlicht"
        signInText="melde dich an, um mit deinem Namen hochzuladen"
        onAnonymous={() => {
          setAuthOpen(false);
          setUploadOpen(true);
        }}
        onSignIn={() => navigate("/anmelden?mode=login")}
        onCancel={() => setAuthOpen(false)}
      />

      <Lightbox photos={photos} index={lightbox} onClose={() => setLightbox(null)} onIndex={setLightbox} />
    </>
  );
}

/** Measures a container's content width, kept in sync via ResizeObserver. */
function useContainerWidth<T extends HTMLElement>(): [RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWidth(el.clientWidth);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function JustifiedGallery({
  photos,
  onOpen,
}: {
  photos: CommunityImage[];
  onOpen: (index: number) => void;
}) {
  const [ref, width] = useContainerWidth<HTMLDivElement>();
  const gap = 12;
  // Shorter rows on narrow viewports so mobile doesn't get one photo per row.
  const targetHeight = width > 0 && width < 640 ? 150 : 240;
  const rows = justifyRows(photos, width, targetHeight, gap);

  // Flat running index so a tile can map back to its position in `photos`.
  let running = -1;

  return (
    <div ref={ref} className="mt-8 flex flex-col" style={{ gap }}>
      {rows.map((row, r) => (
        <div key={r} className="flex" style={{ gap }}>
          {row.map((tile) => {
            running += 1;
            const index = running;
            return (
              <button
                key={tile.photo.id}
                type="button"
                onClick={() => onOpen(index)}
                style={{ width: tile.width, height: tile.height }}
                className="group relative shrink-0 overflow-hidden rounded-2xl bg-band"
              >
                <img
                  src={resolveMediaUrl(tile.photo.url)}
                  alt={tile.photo.credit ?? ""}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                  loading="lazy"
                />
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function GalleryEmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="mt-10 grid place-items-center rounded-3xl border border-dashed border-line bg-band/40 px-6 py-16 text-center">
      <span aria-hidden="true" className="grid h-16 w-16 place-items-center rounded-full bg-white text-teal shadow-sm">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="5" width="18" height="14" rx="2.5" />
          <circle cx="8.5" cy="10" r="1.6" />
          <path d="m4 17 4.5-4.5a2 2 0 0 1 2.8 0L16 17" />
          <path d="m14 15 1.8-1.8a2 2 0 0 1 2.8 0L21 15" />
        </svg>
      </span>
      <p className="mt-5 text-title font-semibold text-ink">Noch keine Fotos von diesem Spot</p>
      <p className="mt-2 max-w-[42ch] text-body text-muted">
        Teile deine schönsten Momente — deine Bilder erscheinen hier in der
        Community-Galerie.
      </p>
      <button
        type="button"
        onClick={onAdd}
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-teal px-5 py-2.5 text-label font-medium text-white transition-colors hover:bg-teal-hover"
      >
        <PlusIcon className="text-[18px]" />
        Foto hinzufügen
      </button>
    </div>
  );
}

/** Full-screen photo viewer. A dark scrim is intentional here (a lightbox is a
 *  focused viewer, not the blurred bottom-sheet), layered above the overlay
 *  panel. Esc/‹/›/click-out; the Esc listener is capture-phase + stops
 *  propagation so it closes the lightbox without also closing the gallery. */
function Lightbox({
  photos,
  index,
  onClose,
  onIndex,
}: {
  photos: CommunityImage[];
  index: number | null;
  onClose: () => void;
  onIndex: (index: number) => void;
}) {
  const reduce = useReducedMotion();
  const open = index !== null;
  const step = useCallback(
    (delta: number) => {
      if (index === null || photos.length === 0) return;
      onIndex((index + delta + photos.length) % photos.length);
    },
    [index, photos.length, onIndex]
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        onClose();
      } else if (e.key === "ArrowRight") {
        step(1);
      } else if (e.key === "ArrowLeft") {
        step(-1);
      }
    };
    // Capture phase so this runs before OverlayPanel's window listener and can
    // stop it — Esc closes the lightbox, not the whole gallery.
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, step, onClose]);

  const photo = index !== null ? photos[index] : undefined;
  const many = photos.length > 1;

  return createPortal(
    <AnimatePresence>
      {open && photo && (
        <motion.div
          key="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Foto-Ansicht"
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/85 p-4 sm:p-10"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.2 }}
          onClick={onClose}
        >
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="absolute right-4 top-4 grid h-11 w-11 place-items-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20 sm:right-6 sm:top-6"
          >
            <CloseIcon width={20} height={20} />
          </button>

          {many && (
            <>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); step(-1); }}
                aria-label="Vorheriges Bild"
                className="absolute left-3 grid h-12 w-12 place-items-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20 sm:left-6"
              >
                <ChevronLeftIcon width={22} height={22} />
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); step(1); }}
                aria-label="Nächstes Bild"
                className="absolute right-3 grid h-12 w-12 place-items-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20 sm:right-6"
              >
                <ChevronRightIcon width={22} height={22} />
              </button>
            </>
          )}

          <motion.img
            key={photo.id}
            src={resolveMediaUrl(photo.url)}
            alt={photo.credit ?? ""}
            className="max-h-full max-w-full rounded-lg object-contain"
            onClick={(e) => e.stopPropagation()}
            initial={reduce ? false : { opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: reduce ? 0 : 0.18 }}
          />

          {(photo.credit || photo.license_name || photo.source_url) && (
            <p className="absolute bottom-4 left-0 right-0 px-4 text-center text-caption text-white/70">
              {photo.credit && <span>Foto: {photo.credit}</span>}
              {photo.license_name && (
                <span>
                  {photo.credit ? " · " : ""}
                  {photo.license_url ? (
                    <a href={photo.license_url} target="_blank" rel="noreferrer noopener" className="underline hover:text-white">
                      {photo.license_name}
                    </a>
                  ) : (
                    photo.license_name
                  )}
                </span>
              )}
              {photo.source_url && (
                <span>
                  {" · "}
                  <a href={photo.source_url} target="_blank" rel="noreferrer noopener" className="underline hover:text-white">
                    Quelle
                  </a>
                </span>
              )}
            </p>
          )}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
