// Type-to-confirm dialog for irreversible hard deletes. A destructive action
// with permanent consequences must not hide behind a one-click toast: the
// operator sees exactly what is removed and has to type the object's name to
// arm the button. Archiving remains the reversible default elsewhere.

import { useState } from "react";
import Modal from "../ui/Modal";

export default function DeleteConfirmDialog({
  open,
  name,
  consequences,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  /** Exact object name the operator must type to confirm. */
  name: string;
  /** What is permanently removed (shown as a warning line). */
  consequences: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState("");
  const armed = typed.trim() === name.trim() && !busy;

  return (
    <Modal
      open={open}
      onClose={onCancel}
      labelledBy="delete-confirm-title"
      describedBy="delete-confirm-body"
      cardClassName="max-w-md rounded-lg bg-admin-surface p-6"
    >
      <h2 id="delete-confirm-title" className="text-ui font-semibold text-admin-danger">
        {name} endgültig löschen?
      </h2>
      <p id="delete-confirm-body" className="mt-2 text-label text-admin-fg2">
        {consequences} Das lässt sich <strong className="text-admin-fg">nicht rückgängig</strong> machen —
        zum Ausblenden lieber „Archivieren" verwenden.
      </p>
      <label className="mt-4 block text-label text-admin-fg2">
        Tippe zur Bestätigung den Namen <span className="admin-mono text-admin-fg">{name}</span>:
        <input
          autoFocus
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          className="mt-1.5 w-full rounded-md border border-admin-border-strong bg-admin-surface px-3 py-2 text-ui text-admin-fg outline-none transition-colors placeholder:text-admin-faint focus:border-admin-danger"
          placeholder={name}
        />
      </label>
      <div className="mt-5 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
        >
          Abbrechen
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={!armed}
          className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-1.5 text-label font-semibold text-admin-danger transition-colors hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Löschen…" : "Endgültig löschen"}
        </button>
      </div>
    </Modal>
  );
}
