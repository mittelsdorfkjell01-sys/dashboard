import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { CloseIcon } from "../lib/icons";
import { getLenis, prefersReducedMotion } from "../lib/lenis";

const SLIDE_MS = 340;
const SLIDE_EASE = "cubic-bezier(0.22, 1, 0.36, 1)";

/**
 * Shared bottom-sheet chassis for the Fotogalerie/Kommentare overlays. Slides up
 * from the bottom on a native CSS `transform` transition (compositor-driven, so
 * it stays smooth on iOS — framer's drag element used to animate on the main
 * thread and stuttered).
 *
 *  - `sm:` and up: a content-sized panel floating over a blurred (never
 *    darkened) page.
 *  - below `sm:`: a full-screen sheet.
 *
 * Closes via the pill (tap), a click on the blurred area (desktop), Esc, or —
 * with `mobileDragToClose` — a downward swipe anywhere on the sheet, but only
 * once it is scrolled to the very top (so scrolling a tall gallery still works).
 * Traps Tab focus, returns focus to the trigger, and restores the page's scroll
 * position on close so the visitor lands back where they opened it.
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
  const reduce = prefersReducedMotion();
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const requestClose = useCallback(() => onCloseRef.current(), []);

  // Native-CSS slide: `mounted` keeps the node through the close animation,
  // `slidIn` toggles the transform a frame after mount so it actually animates.
  const [mounted, setMounted] = useState(open);
  const [slidIn, setSlidIn] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      return;
    }
    setSlidIn(false);
    const timer = window.setTimeout(() => setMounted(false), reduce ? 0 : SLIDE_MS);
    return () => window.clearTimeout(timer);
  }, [open, reduce]);

  useEffect(() => {
    if (!mounted || !open) return;
    let inner = 0;
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => setSlidIn(true));
    });
    return () => {
      cancelAnimationFrame(outer);
      if (inner) cancelAnimationFrame(inner);
    };
  }, [mounted, open]);

  // Lock scrolling while open and, crucially, restore the exact scroll position
  // on close — otherwise the overflow-lock (and Lenis re-sync) can drop the page
  // back to the top instead of where the overlay was opened from.
  useEffect(() => {
    if (!open) return;
    const { body, documentElement } = document;
    const appRoot = document.getElementById("root");
    const lenis = getLenis();
    const scrollY = window.scrollY;
    const prevOverflow = body.style.overflow;
    const prevHtmlOverflow = documentElement.style.overflow;
    const prevPaddingRight = body.style.paddingRight;
    const rootWasInert = appRoot?.inert ?? false;
    const scrollbar = window.innerWidth - documentElement.clientWidth;

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
      if (lenis) lenis.scrollTo(scrollY, { immediate: true, force: true });
      else window.scrollTo(0, scrollY);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    panelRef.current?.focus({ preventScroll: true });
    return () => {
      trigger?.focus({ preventScroll: true });
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

  // Imperative swipe-to-close (touch only). The panel is itself the scroller, so
  // the gesture only becomes a close when it is scrolled to the very top and the
  // thumb travels down; otherwise it scrolls normally. Fully imperative (no React
  // re-render per frame) so the follow is as smooth as the slide.
  const drag = useRef({ startY: 0, lastY: 0, lastT: 0, vy: 0, active: false });
  const bodyStart = useRef<{ y: number; id: number } | null>(null);
  const moveRaf = useRef(0);
  const pendingY = useRef(0);

  const beginDrag = (clientY: number, el: HTMLElement, pointerId: number) => {
    drag.current = { startY: clientY, lastY: clientY, lastT: performance.now(), vy: 0, active: true };
    if (panelRef.current) panelRef.current.style.transition = "none";
    try {
      el.setPointerCapture(pointerId);
    } catch {
      /* older Safari still works via the element's own events */
    }
  };
  const moveDrag = (clientY: number) => {
    const d = drag.current;
    if (!d.active) return;
    const now = performance.now();
    const dt = now - d.lastT;
    if (dt > 0) d.vy = (clientY - d.lastY) / dt;
    d.lastY = clientY;
    d.lastT = now;
    pendingY.current = clientY;
    if (!moveRaf.current) {
      moveRaf.current = requestAnimationFrame(() => {
        moveRaf.current = 0;
        const el = panelRef.current;
        if (el && drag.current.active) {
          el.style.transform = `translateY(${Math.max(0, pendingY.current - drag.current.startY)}px)`;
        }
      });
    }
  };
  const endDrag = () => {
    const d = drag.current;
    if (!d.active) return;
    d.active = false;
    if (moveRaf.current) {
      cancelAnimationFrame(moveRaf.current);
      moveRaf.current = 0;
    }
    const dy = d.lastY - d.startY;
    const closing = dy > 120 || (dy > 40 && d.vy > 0.6);
    const el = panelRef.current;
    if (el) {
      el.style.transition = reduce ? "none" : `transform ${SLIDE_MS}ms ${SLIDE_EASE}`;
      el.style.transform = reduce ? "" : closing ? "translateY(100%)" : "translateY(0)";
    }
    if (closing) requestClose();
  };

  const onPanelPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!mobileDragToClose || e.pointerType !== "touch") return;
    bodyStart.current = { y: e.clientY, id: e.pointerId };
  };
  const onPanelPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!mobileDragToClose) return;
    if (drag.current.active) {
      moveDrag(e.clientY);
      return;
    }
    const bs = bodyStart.current;
    if (!bs) return;
    if (e.currentTarget.scrollTop <= 0 && e.clientY - bs.y > 14) {
      beginDrag(bs.y, e.currentTarget, bs.id);
      moveDrag(e.clientY);
    }
  };
  const onPanelPointerEnd = () => {
    bodyStart.current = null;
    endDrag();
  };

  if (!mounted) return null;

  const panelStyle: CSSProperties = reduce
    ? {}
    : {
        transform: slidIn ? "translateY(0)" : "translateY(100%)",
        transition: drag.current.active ? "none" : `transform ${SLIDE_MS}ms ${SLIDE_EASE}`,
        willChange: "transform",
      };

  return createPortal(
    <>
      <div
        aria-hidden="true"
        className="fixed inset-0 z-[1100] hidden bg-[var(--sw-overlay-soft)] backdrop-blur-[2px] sm:block"
        style={{ opacity: slidIn ? 1 : 0, transition: `opacity ${reduce ? 0 : 200}ms ease` }}
        onClick={requestClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        data-lenis-prevent
        className="fixed inset-0 z-[1101] overflow-y-auto bg-page outline-none sm:inset-x-4 sm:bottom-0 sm:top-auto sm:mx-auto sm:min-h-[50vh] sm:max-h-[88vh] sm:max-w-[1570px] sm:rounded-t-3xl sm:border-x sm:border-t sm:border-line"
        style={panelStyle}
        onPointerDown={onPanelPointerDown}
        onPointerMove={onPanelPointerMove}
        onPointerUp={onPanelPointerEnd}
        onPointerCancel={onPanelPointerEnd}
      >
        <div className="sticky top-0 z-10 flex justify-center bg-page px-5 py-3 sm:bg-page/95 sm:px-8 sm:backdrop-blur">
          <button
            type="button"
            onClick={requestClose}
            aria-label={mobileDragToClose ? "Galerie schließen (oder herunterwischen)" : undefined}
            className={`min-h-11 min-w-11 items-center justify-center text-label font-medium text-muted transition-colors hover:text-ink ${mobileDragToClose ? "flex sm:inline-flex" : "inline-flex gap-1.5"}`}
          >
            {mobileDragToClose ? <><span aria-hidden className="h-1 w-10 rounded-full bg-ink sm:hidden" /><span className="hidden items-center gap-1.5 sm:inline-flex"><CloseIcon width={15} height={15} />Schließen</span></> : <><CloseIcon width={15} height={15} />Schließen</>}
          </button>
        </div>
        <div className="px-5 pb-8 pt-5 sm:px-8 sm:pb-10 sm:pt-6">{children}</div>
      </div>
    </>,
    document.body
  );
}
