import Modal from "../ui/Modal";
import Button from "../ui/Button";

/**
 * Shown when a PATCH is rejected with 409 because someone else edited the same
 * spot/region since this form loaded it (optimistic locking — this is a
 * multi-operator tool). No auto-merge: the operator explicitly chooses to
 * discard their edits and reload the fresh version, or to overwrite it.
 */
export default function ConflictDialog({
  open,
  onReload,
  onOverwrite,
  onClose,
  busy = false,
}: {
  open: boolean;
  /** Discard local edits and re-fetch the server version. */
  onReload: () => void;
  /** Re-send the save, forcing over the newer version. */
  onOverwrite: () => void;
  onClose: () => void;
  busy?: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} labelledBy="conflict-title">
      <h2 id="conflict-title" className="text-ui font-semibold text-ink">
        Inzwischen von jemand anderem geändert
      </h2>
      <p className="mt-2 text-label text-ink-soft">
        Dieser Datensatz wurde bearbeitet, seit du das Formular geöffnet hast.
        Wenn du jetzt speicherst, überschreibst du die neueren Änderungen. Lade
        die aktuelle Version neu (deine Eingaben gehen verloren) oder
        überschreibe bewusst.
      </p>
      <div className="mt-5 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={onReload} disabled={busy}>
          Neu laden
        </Button>
        <Button variant="danger" onClick={onOverwrite} disabled={busy}>
          {busy ? "Speichern…" : "Trotzdem überschreiben"}
        </Button>
      </div>
    </Modal>
  );
}
