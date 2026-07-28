import Modal from "./Modal";
import Button from "./Button";

/**
 * Reusable confirm dialog — the accessible replacement for `window.confirm`.
 * Defaults to a destructive (danger) confirm button.
 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "Löschen",
  variant = "danger",
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message?: string;
  confirmText?: string;
  variant?: "danger" | "primary";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} labelledBy="confirm-title">
      <h2 id="confirm-title" className="text-ui font-semibold text-ink">
        {title}
      </h2>
      {message && <p className="mt-2 text-label text-ink-soft">{message}</p>}
      <div className="mt-5 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          Abbrechen
        </Button>
        <Button variant={variant} onClick={onConfirm} disabled={busy}>
          {busy ? "…" : confirmText}
        </Button>
      </div>
    </Modal>
  );
}
