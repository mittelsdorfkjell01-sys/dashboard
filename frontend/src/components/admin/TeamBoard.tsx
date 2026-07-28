import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createTeamNote,
  deleteTeamNote,
  getTeamNotes,
  type TeamNote,
} from "../../lib/api";
import { Button, Input } from "../ui";

/**
 * Team-notes composer + board (Sprint 4). Lives on the Übersicht — the notes
 * are the team's shared message wall, so composing them belongs next to where
 * they're read rather than on the user-management page.
 */
export default function TeamBoard() {
  const [notes, setNotes] = useState<TeamNote[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => getTeamNotes().then(setNotes).catch(() => {});
  useEffect(() => {
    void load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createTeamNote(body.trim());
      setBody("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await deleteTeamNote(id).catch(() => {});
    await load();
  };

  return (
    <section className="mt-6">
      <h2 className="text-body font-semibold text-ink">Team-Notizen</h2>
      <p className="mt-1 text-label text-muted">Kurze Nachrichten fürs Team.</p>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <Input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Nachricht fürs Team…"
        />
        <Button type="submit" disabled={busy || !body.trim()} className="shrink-0">
          Posten
        </Button>
      </form>
      {error && <p className="mt-2 text-label text-red-600">{error}</p>}
      {notes.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((n) => (
            <div
              key={n.id}
              className="flex items-start justify-between gap-2 rounded-2xl border border-line bg-teal/5 p-4"
            >
              <div className="min-w-0">
                <p className="whitespace-pre-wrap text-ui text-ink">{n.body}</p>
                <p className="mt-1 text-caption text-muted">
                  {n.author ?? "—"} · {new Date(n.created_at).toLocaleString("de-DE")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => remove(n.id)}
                className="shrink-0 text-caption text-muted hover:text-red-600"
                aria-label="Notiz löschen"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
