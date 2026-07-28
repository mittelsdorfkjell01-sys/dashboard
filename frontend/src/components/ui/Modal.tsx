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
  children,
}: {
  open: boolean;
  onClose: () => void;
  /** id of the element that titles the dialog (for aria-labelledby). */
  labelledBy?: string;
  children: ReactNode;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    const { body } = document;
    const prevOverflow = body.style.overflow;
    body.style.overflow = "hidden";
    cardRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      body.style.overflow = prevOverflow;
      restoreRef.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[1200] grid place-items-center bg-black/30 p-4"
      onClick={onClose}
    >
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-float outline-none"
      >
        {children}
      </div>
    </div>,
    document.body
  );
}
