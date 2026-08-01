// Kanban board body (Sprint 8), extracted so it can render both as the
// standalone /admin/board page and embedded on the Übersicht. This component is
// heading-less — the caller supplies whatever title/chrome fits its context.

import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createBoardTask,
  deleteBoardTask,
  getBoardTasks,
  updateBoardTask,
  type BoardTask,
} from "../../lib/api";
import { Button, Input, Textarea } from "../ui";
import PromptDialog from "../ui/PromptDialog";
import ConfirmDialog from "../ui/ConfirmDialog";

type Status = "open" | "done";
const COLUMNS: { key: Status; label: string }[] = [
  { key: "open", label: "Offen" },
  { key: "done", label: "Erledigt" },
];

export default function BoardPanel() {
  const [tasks, setTasks] = useState<BoardTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<Status | null>(null);
  const [editTarget, setEditTarget] = useState<BoardTask | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BoardTask | null>(null);
  const [dialogBusy, setDialogBusy] = useState(false);

  const load = () =>
    getBoardTasks()
      .then(setTasks)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Board laden fehlgeschlagen.")
      );
  useEffect(() => {
    void load();
  }, []);

  const move = async (task: BoardTask, status: Status) => {
    if (task.status === status) return;
    // Optimistic move so the drag feels instant.
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status } : t)));
    try {
      await updateBoardTask(task.id, { status });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verschieben fehlgeschlagen.");
      void load();
    }
  };

  const rename = async (title: string) => {
    if (!editTarget) return;
    setDialogBusy(true);
    try {
      await updateBoardTask(editTarget.id, { title: title.trim() });
      setEditTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Umbenennen fehlgeschlagen.");
    } finally {
      setDialogBusy(false);
    }
  };

  const remove = async () => {
    if (!deleteTarget) return;
    setDialogBusy(true);
    try {
      await deleteBoardTask(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen.");
    } finally {
      setDialogBusy(false);
    }
  };

  return (
    <div>
      {error && (
        <div role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700">
          {error}
        </div>
      )}

      <NewTaskForm onCreated={load} onError={setError} />

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {COLUMNS.map((col) => {
          const items = tasks.filter((t) => t.status === col.key);
          return (
            <div
              key={col.key}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(col.key);
              }}
              onDragLeave={() => setDragOver((c) => (c === col.key ? null : c))}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(null);
                const tid = e.dataTransfer.getData("text/plain");
                const task = tasks.find((t) => t.id === tid);
                if (task) void move(task, col.key);
              }}
              className={`rounded-2xl border p-3 transition-colors ${
                dragOver === col.key ? "border-teal bg-teal/5" : "border-line bg-band/40"
              }`}
            >
              <div className="flex items-center justify-between px-1">
                <p className="text-label font-semibold text-ink">{col.label}</p>
                <span className="text-caption text-muted">{items.length}</span>
              </div>
              <div className="mt-2 space-y-2">
                {items.length === 0 ? (
                  <p className="px-1 py-6 text-center text-caption text-muted">Keine Aufgaben.</p>
                ) : (
                  items.map((t) => (
                    <TaskCard
                      key={t.id}
                      task={t}
                      onMove={(s) => move(t, s)}
                      onEdit={() => setEditTarget(t)}
                      onDelete={() => setDeleteTarget(t)}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      <PromptDialog
        open={editTarget !== null}
        title="Aufgabe umbenennen"
        confirmText="Speichern"
        initialValue={editTarget?.title ?? ""}
        busy={dialogBusy}
        onConfirm={rename}
        onCancel={() => setEditTarget(null)}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Aufgabe löschen"
        message={deleteTarget ? `„${deleteTarget.title}" wird gelöscht.` : undefined}
        busy={dialogBusy}
        onConfirm={remove}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

function TaskCard({
  task,
  onMove,
  onEdit,
  onDelete,
}: {
  task: BoardTask;
  onMove: (status: Status) => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", task.id)}
      className="cursor-grab rounded-lg border border-line bg-white p-3 active:cursor-grabbing"
    >
      <p className="text-label font-medium text-ink">{task.title}</p>
      {task.body && <p className="mt-1 whitespace-pre-wrap text-caption text-muted">{task.body}</p>}
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-caption text-muted">{task.author ?? "—"}</span>
        <div className="flex items-center gap-2 text-caption">
          {task.status === "open" ? (
            <button type="button" onClick={() => onMove("done")} className="font-medium text-teal hover:underline">
              → Erledigt
            </button>
          ) : (
            <button type="button" onClick={() => onMove("open")} className="font-medium text-teal hover:underline">
              ← Offen
            </button>
          )}
          <button type="button" onClick={onEdit} className="text-muted hover:text-ink">
            Bearbeiten
          </button>
          <button type="button" onClick={onDelete} className="text-muted hover:text-red-600">
            Löschen
          </button>
        </div>
      </div>
    </div>
  );
}

function NewTaskForm({
  onCreated,
  onError,
}: {
  onCreated: () => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await createBoardTask(title.trim(), body.trim() || undefined);
      setTitle("");
      setBody("");
      await onCreated();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="rounded-2xl bg-ink/5 p-4">
      <p className="text-label font-semibold text-ink">Neue Aufgabe</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_2fr_auto]">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titel" />
        <Textarea
          className="min-h-[40px] resize-y"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Details (optional)"
        />
        <Button type="submit" disabled={busy || !title.trim()} className="shrink-0 self-start">
          {busy ? "…" : "Anlegen"}
        </Button>
      </div>
    </form>
  );
}
