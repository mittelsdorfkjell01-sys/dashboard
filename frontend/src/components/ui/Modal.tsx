import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

// Nested modals used to leave their background inert. Each modal snapshotted
// body.children on open and restored to that snapshot on close, so when a
// dialog opened on top of another the outer modal recorded (correctly)
// "no inert", the inner recorded "outer already inert" and — because the
// order of React's effect cleanups on simultaneous unmount is not the
// unmount order the fix relies on — the root ended up permanently inert.
//
// Fix: a module-level counter and a WeakMap of original inert values. The
// first modal opening captures + inerts, subsequent modals only bump the
// counter, and only the last modal closing restores. `body` overflow uses
// the same shape so nested modals never fight over it either.
let modalStackDepth = 0;
const inertOriginals = new WeakMap<HTMLElement, boolean>();
let bodyOverflowOriginal = "";

function pushModalLock(overlay: HTMLElement | null): void {
  if (modalStackDepth === 0) {
    const body = document.body;
    bodyOverflowOriginal = body.style.overflow;
    body.style.overflow = "hidden";
    for (const child of Array.from(body.children)) {
      const el = child as HTMLElement;
      if (el === overlay) continue;
      inertOriginals.set(el, el.inert);
      el.inert = true;
    }
  }
  modalStackDepth += 1;
}

function popModalLock(): void {
  modalStackDepth -= 1;
  if (modalStackDepth <= 0) {
    modalStackDepth = 0;
    const body = document.body;
    body.style.overflow = bodyOverflowOriginal;
    for (const child of Array.from(body.children)) {
      const el = child as HTMLElement;
      const original = inertOriginals.get(el);
      if (original !== undefined) {
        el.inert = original;
        inertOriginals.delete(el);
      } else {
        // A body child that appeared after the first modal opened — never
        // captured, so it should not carry lingering inert either.
        el.inert = false;
      }
    }
  }
}

/**
 * Minimal centered modal chassis for admin dialogs (conflict / confirm /
 * prompt). Scrim + a white card; closes on Esc or a scrim click; traps focus
 * and restores it to the trigger on close. No animation library — admin
 * dialogs are utilitarian, not the public bottom-sheet overlays.
 */
export default function Modal({
  open,
  onClose,
  labelledBy,
  describedBy,
  children,
  cardClassName = "max-w-md rounded-lg bg-surface p-6",
}: {
  open: boolean;
  onClose: () => void;
  /** id of the element that titles the dialog (for aria-labelledby). */
  labelledBy?: string;
  /** id of optional explanatory content inside the dialog. */
  describedBy?: string;
  children: ReactNode;
  /** Size and surface of the card. Confirm/prompt dialogs keep the default
   *  narrow white box; the media picker needs a near-full-screen working
   *  surface in the admin theme. Everything else — focus trap, Esc, inert
   *  background, scroll lock — is shared. */
  cardClassName?: string;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  // Hold the latest onClose without it being an effect dependency — otherwise a
  // new inline onClose on every parent render (e.g. while typing in a dialog
  // input) would re-run the effect, and its cleanup would yank focus out of the
  // field after each keystroke.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    pushModalLock(overlayRef.current);
    const focusable = () =>
      Array.from(
        cardRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ) ?? []
      ).filter((element) => !element.hasAttribute("hidden"));
    (focusable()[0] ?? cardRef.current)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
      if (e.key === "Tab") {
        const items = focusable();
        if (!items.length) {
          e.preventDefault();
          cardRef.current?.focus();
          return;
        }
        const first = items[0];
        const last = items[items.length - 1];
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
    return () => {
      window.removeEventListener("keydown", onKey);
      popModalLock();
      restoreRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[1200] grid place-items-center bg-black/30 p-4"
      onClick={onClose}
    >
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        data-lenis-prevent
        className={`w-full shadow-float outline-none ${cardClassName}`}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}
