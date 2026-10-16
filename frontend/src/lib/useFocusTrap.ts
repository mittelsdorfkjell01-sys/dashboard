import { useEffect, type RefObject } from "react";

/**
 * Minimal focus management for dialogs rendered outside the shared <Modal>
 * chassis (the framer-motion comment/suggest portals). While `open`:
 *  - moves focus into `containerRef` on open — unless focus is already inside
 *    (so a field with `autoFocus` keeps it);
 *  - traps Tab / Shift+Tab within the container;
 *  - restores focus to the previously focused element on close.
 *
 * Escape handling stays with the caller — these dialogs already own it. The
 * container should carry `tabIndex={-1}` so it can hold focus when it has no
 * focusable children yet.
 */
export function useFocusTrap(open: boolean, containerRef: RefObject<HTMLElement>): void {
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const container = containerRef.current;

    const focusables = () =>
      Array.from(
        container?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => !el.hasAttribute("hidden") && el.offsetParent !== null);

    // Don't steal focus from an element the dialog already focused (autoFocus).
    if (container && !container.contains(document.activeElement)) {
      (focusables()[0] ?? container).focus();
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) {
        e.preventDefault();
        container?.focus();
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
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previouslyFocused?.focus();
    };
  }, [open, containerRef]);
}
