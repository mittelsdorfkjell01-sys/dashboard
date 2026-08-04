// Inline confirm banner: a non-modal "are you sure?" strip shown at the top of a
// surface. The action only runs when the operator clicks the ✓ (Haken); ✕ aborts.
// Used for the destructive spot actions (archive / delete) on the map and editor.

export default function ConfirmBar({
  message,
  busy = false,
  tone = "warning",
  onConfirm,
  onCancel,
}: {
  message: string;
  busy?: boolean;
  tone?: "warning" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const toneCls =
    tone === "danger"
      ? "border-admin-danger-border bg-admin-danger-bg text-admin-danger"
      : "border-admin-warning-bg bg-admin-warning-bg text-admin-warning";
  return (
    <div
      role="alert"
      className={`flex items-center justify-between gap-3 rounded-md border px-3 py-2 ${toneCls}`}
    >
      <span className="text-label font-medium">{message}</span>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          aria-label="Bestätigen"
          title="Bestätigen"
          className="grid h-7 w-7 place-items-center rounded-md bg-admin-primary text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
        >
          <span aria-hidden className="text-[15px] leading-none">✓</span>
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          aria-label="Abbrechen"
          title="Abbrechen"
          className="grid h-7 w-7 place-items-center rounded-md border border-admin-border bg-admin-surface text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
        >
          <span aria-hidden className="text-[13px] leading-none">✕</span>
        </button>
      </div>
    </div>
  );
}
