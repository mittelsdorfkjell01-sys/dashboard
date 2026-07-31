import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createTeamNote,
  deleteTeamNote,
  getTeamNotes,
  updateTeamNote,
  type TeamNote,
  type TeamNotePriority,
} from "../../lib/api";
import { Button, Input, Select, Textarea } from "../ui";
import Modal from "../ui/Modal";
import ConfirmDialog from "../ui/ConfirmDialog";

/**
 * Team-notes board on the Übersicht — the team's shared message wall (Sprint 4).
 * Each note carries a priority: "important" notes get a red stroke and sort to
 * the top; "normal" ones look as before. Per-tile actions (Bearbeiten / Löschen)
 * live behind a three-dot menu in the tile's top-right corner rather than
 * cluttering the tile itself.
 */
export default function TeamBoard() {
  const [notes, setNotes] = useState<TeamNote[]>([]);
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState<TeamNotePriority>("normal");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Per-tile three-dot menu (id of the open one, or null).
  const [menuId, setMenuId] = useState<string | null>(null);
  // Edit / delete dialog targets.
  const [editTarget, setEditTarget] = useState<TeamNote | null>(null);
  const [editBody, setEditBody] = useState("");
  const [editPriority, setEditPriority] = useState<TeamNotePriority>("normal");
  const [deleteTarget, setDeleteTarget] = useState<TeamNote | null>(null);
  const [dialogBusy, setDialogBusy] = useState(false);

  const load = () => getTeamNotes().then(setNotes).catch(() => {});
  useEffect(() => {
    void load();
  }, []);

  // Close the open tile menu on an outside click.
  useEffect(() => {
    if (!menuId) return;
    const onDoc = () => setMenuId(null);
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuId]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createTeamNote(body.trim(), priority);
      setBody("");
      setPriority("normal");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const openEdit = (n: TeamNote) => {
    setMenuId(null);
    setEditTarget(n);
    setEditBody(n.body);
    setEditPriority(n.priority);
  };

  const saveEdit = async () => {
    if (!editTarget || !editBody.trim()) return;
    setDialogBusy(true);
    try {
      await updateTeamNote(editTarget.id, {
        body: editBody.trim(),
        priority: editPriority,
      });
      setEditTarget(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setDialogBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDialogBusy(true);
    try {
      await deleteTeamNote(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch {
      // Non-critical; leave the tile in place on failure.
    } finally {
      setDialogBusy(false);
    }
  };

  return (
    <section className="mt-6">
      <h2 className="text-body font-semibold text-ink">Team-Notizen</h2>
      <p className="mt-1 text-label text-muted">Kurze Nachrichten fürs Team.</p>

      <form onSubmit={submit} className="mt-3 flex flex-wrap gap-2">
        <Input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Nachricht fürs Team…"
          className="min-w-[200px] flex-1"
        />
        <Select
          value={priority}
          onChange={(e) => setPriority(e.target.value as TeamNotePriority)}
          aria-label="Priorität"
          className="shrink-0"
        >
          <option value="normal">Normal</option>
          <option value="important">Wichtig</option>
        </Select>
        <Button type="submit" disabled={busy || !body.trim()} className="shrink-0">
          Posten
        </Button>
      </form>
      {error && <p className="mt-2 text-label text-red-600">{error}</p>}

      {notes.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((n) => {
            const important = n.priority === "important";
            return (
              <div
                key={n.id}
                className={`relative rounded-2xl p-4 ${
                  important
                    ? "border-2 border-red-400 bg-red-50/40"
                    : "border border-line bg-teal/5"
                }`}
              >
                {/* Three-dot menu, top-right. */}
                <div className="absolute right-2 top-2">
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      setMenuId(menuId === n.id ? null : n.id);
                    }}
                    aria-label="Optionen"
                    aria-haspopup="menu"
                    aria-expanded={menuId === n.id}
                    className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-ink/5 hover:text-ink"
                  >
                    <span aria-hidden className="text-lg leading-none">⋯</span>
                  </button>
                  {menuId === n.id && (
                    <div
                      role="menu"
                      onMouseDown={(e) => e.stopPropagation()}
                      className="absolute right-0 z-30 mt-1 w-36 overflow-hidden rounded-lg border border-line bg-white py-1 shadow-float"
                    >
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => openEdit(n)}
                        className="block w-full px-3 py-2 text-left text-label text-ink hover:bg-band/60"
                      >
                        Bearbeiten
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setMenuId(null);
                          setDeleteTarget(n);
                        }}
                        className="block w-full px-3 py-2 text-left text-label text-red-600 hover:bg-red-50"
                      >
                        Löschen
                      </button>
                    </div>
                  )}
                </div>

                <div className="min-w-0 pr-7">
                  <p className="whitespace-pre-wrap text-ui text-ink">{n.body}</p>
                  <p className="mt-1 text-caption text-muted">
                    {n.author ?? "—"} · {new Date(n.created_at).toLocaleString("de-DE")}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit dialog */}
      <Modal
        open={editTarget !== null}
        onClose={() => setEditTarget(null)}
        labelledBy="edit-note-title"
      >
        <h2 id="edit-note-title" className="text-ui font-semibold text-ink">
          Notiz bearbeiten
        </h2>
        <label className="mt-3 block text-label text-ink-soft">Nachricht</label>
        <Textarea
          value={editBody}
          onChange={(e) => setEditBody(e.target.value)}
          rows={3}
          className="mt-1"
        />
        <label className="mt-3 block text-label text-ink-soft">Priorität</label>
        <Select
          value={editPriority}
          onChange={(e) => setEditPriority(e.target.value as TeamNotePriority)}
          aria-label="Priorität"
          className="mt-1"
        >
          <option value="normal">Normal</option>
          <option value="important">Wichtig</option>
        </Select>
        <div className="mt-5 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => setEditTarget(null)} disabled={dialogBusy}>
            Abbrechen
          </Button>
          <Button onClick={saveEdit} disabled={dialogBusy || !editBody.trim()}>
            {dialogBusy ? "…" : "Speichern"}
          </Button>
        </div>
      </Modal>

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Notiz löschen?"
        message="Diese Team-Notiz wird dauerhaft entfernt."
        busy={dialogBusy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
}
