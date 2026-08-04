// Floating confirm toast — an Apple-style notification that patches in from the
// top-right, above the whole UI (portaled to <body>, which carries `.admin-scope`
// so the admin tokens resolve). Used to confirm destructive spot actions
// (archive / delete): the action only runs on ✓, ✕ dismisses.

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

export default function ConfirmToast({
  open,
  message,
  tone = "warning",
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  message: string;
  tone?: "warning" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  // Drive the slide-in: mount hidden, then flip on the next frame so the
  // transition plays ("patches in").
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!open) {
      setShown(false);
      return;
    }
    const id = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(id);
  }, [open]);

  if (!open) return null;

  const accent = tone === "danger" ? "text-admin-danger" : "text-admin-warning";
  return createPortal(
    <div className="pointer-events-none fixed right-4 top-4 z-[1300] flex justify-end">
      <div
        role="alertdialog"
        aria-label={message}
        className={`pointer-events-auto flex w-[320px] max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-admin-border bg-admin-elevated p-3.5 shadow-float transition-all duration-300 ease-out ${
          shown ? "translate-x-0 opacity-100" : "translate-x-6 opacity-0"
        }`}
      >
        <p className={`flex-1 text-label font-semibold ${accent}`}>{message}</p>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            aria-label="Bestätigen"
            title="Bestätigen"
            className="grid h-8 w-8 place-items-center rounded-lg bg-admin-primary text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
          >
            <span aria-hidden className="text-[16px] leading-none">✓</span>
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            aria-label="Abbrechen"
            title="Abbrechen"
            className="grid h-8 w-8 place-items-center rounded-lg border border-admin-border bg-admin-surface text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
          >
            <span aria-hidden className="text-[13px] leading-none">✕</span>
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
