import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

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
}: {
  open: boolean;
  onClose: () => void;
  /** id of the element that titles the dialog (for aria-labelledby). */
  labelledBy?: string;
  /** id of optional explanatory content inside the dialog. */
  describedBy?: string;
  children: ReactNode;
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
    const { body } = document;
    const prevOverflow = body.style.overflow;
    body.style.overflow = "hidden";
    const focusable = () =>
      Array.from(
        cardRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ) ?? []
      ).filter((element) => !element.hasAttribute("hidden"));
    (focusable()[0] ?? cardRef.current)?.focus();

    const inerted = Array.from(body.children).filter(
      (element) => element !== overlayRef.current
    ) as HTMLElement[];
    const previousInert = inerted.map((element) => element.inert);
    inerted.forEach((element) => { element.inert = true; });
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
      body.style.overflow = prevOverflow;
      inerted.forEach((element, index) => { element.inert = previousInert[index]; });
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
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-float outline-none"
      >
        {children}
      </div>
    </div>,
    document.body
  );
}
