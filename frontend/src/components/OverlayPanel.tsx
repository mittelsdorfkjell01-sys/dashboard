import { useCallback, useEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useDragControls, useReducedMotion } from "framer-motion";
import { CloseIcon } from "../lib/icons";
import { getLenis } from "../lib/lenis";

/**
 * Shared bottom-sheet chassis for the Fotogalerie/Kommentare overlays (Figma
 * Frame_10/11). Slides up from the bottom (~320ms, ease-out) — always a
 * `y: 100% → 0` transform, so the same animation works for both layouts
 * below without any JS breakpoint branching:
 *
 *  - `sm:` and up: a content-sized panel (never stretched to fill the
 *    screen) floating over the page, which is only blurred behind it, never
 *    darkened — no scrim.
 *  - below `sm:`: a full-screen sheet (`inset-0`) — the blur layer is
 *    dropped here (`hidden sm:block`) since the sheet already covers
 *    everything there is to blur.
 *
 * Closes via the pill, a click on the blurred area (desktop only — there's
 * nothing to click through to on the mobile sheet), or Esc; traps Tab focus
 * inside the panel and returns focus to the trigger on close.
 */
export default function OverlayPanel({
  open,
  onClose,
  triggerRef,
  children,
  mobileDragToClose = false,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  children: ReactNode;
  mobileDragToClose?: boolean;
}) {
  const reduce = useReducedMotion();
  const panelRef = useRef<HTMLDivElement>(null);
  const dragControls = useDragControls();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const requestClose = useCallback(() => {
    onCloseRef.current();
  }, []);

  // Lock both native scrolling and Lenis while the portalled sheet is open.
  // Locking only `body` leaves Lenis' `<html>` scroller active and makes the
  // gallery/comments sheet jump or move with the page behind it.
  useEffect(() => {
    if (!open) return;
    const { body, documentElement } = document;
    const appRoot = document.getElementById("root");
    const lenis = getLenis();
    const prevOverflow = body.style.overflow;
    const prevHtmlOverflow = documentElement.style.overflow;
    const prevPaddingRight = body.style.paddingRight;
    const rootWasInert = appRoot?.inert ?? false;
    const scrollbar = window.innerWidth - document.documentElement.clientWidth;

    lenis?.stop();
    if (appRoot) appRoot.inert = true;
    body.style.overflow = "hidden";
    documentElement.style.overflow = "hidden";
    if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;

    return () => {
      body.style.overflow = prevOverflow;
      documentElement.style.overflow = prevHtmlOverflow;
      body.style.paddingRight = prevPaddingRight;
      if (appRoot) appRoot.inert = rootWasInert;
      lenis?.start();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    panelRef.current?.focus();
    return () => {
      trigger?.focus();
    };
  }, [open, triggerRef]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        requestClose();
        return;
      }
      if (e.key === "Tab") {
        const root = panelRef.current;
        if (!root) return;
        const focusables = root.querySelectorAll<HTMLElement>(
          'button, [href], [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, requestClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="blur"
            aria-hidden="true"
            className="fixed inset-0 z-[1100] hidden bg-[var(--sw-overlay-soft)] backdrop-blur-[2px] sm:block"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.2 }}
            onClick={requestClose}
          />
          <motion.div
            key="panel"
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            tabIndex={-1}
            data-lenis-prevent
            className="fixed inset-0 z-[1101] overflow-y-auto bg-page outline-none sm:inset-x-4 sm:bottom-0 sm:top-auto sm:mx-auto sm:min-h-[50vh] sm:max-h-[88vh] sm:max-w-[1570px] sm:rounded-t-3xl sm:border-x sm:border-t sm:border-line"
            initial={{ y: reduce ? 0 : "100%" }}
            animate={{ y: 0 }}
            exit={{ y: reduce ? 0 : "100%" }}
            transition={{ duration: reduce ? 0 : 0.32, ease: "easeOut" }}
            drag={mobileDragToClose ? "y" : false}
            dragListener={false}
            dragControls={dragControls}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.72 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 850) requestClose();
            }}
          >
            <div className="sticky top-0 z-10 flex justify-center bg-page px-5 py-3 sm:bg-page/95 sm:px-8 sm:backdrop-blur">
              <button
                type="button"
                onClick={requestClose}
                onPointerDown={(event) => mobileDragToClose && dragControls.start(event)}
                aria-label={mobileDragToClose ? "Galerie schließen oder zum Herunterziehen halten" : undefined}
                className={`min-h-11 min-w-11 items-center justify-center text-label font-medium text-muted transition-colors hover:text-ink ${mobileDragToClose ? "flex touch-none sm:inline-flex" : "inline-flex gap-1.5"}`}
              >
                {mobileDragToClose ? <><span aria-hidden className="h-1 w-10 rounded-full bg-ink sm:hidden" /><span className="hidden items-center gap-1.5 sm:inline-flex"><CloseIcon width={15} height={15} />Schließen</span></> : <><CloseIcon width={15} height={15} />Schließen</>}
              </button>
            </div>
            <div className="px-5 pb-8 pt-5 sm:px-8 sm:pb-10 sm:pt-6">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}
