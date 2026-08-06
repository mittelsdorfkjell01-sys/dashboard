// Kanban board body (Sprint 8), extracted so it can render both as the
// standalone /admin/board page and embedded on the Übersicht. This component is
// heading-less — the caller supplies whatever title/chrome fits its context.

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  ApiError,
  createBoardTask,
  deleteBoardTask,
  getBoardTasks,
  updateBoardTask,
  type BoardTask,
} from "../../lib/api";
import { Button, Input, Textarea } from "../ui";
import Modal from "../ui/Modal";
import ConfirmDialog from "../ui/ConfirmDialog";
import UnsavedChangesDialog from "./UnsavedChangesDialog";
import {
  useFormDirty,
  useUnsavedChangesGuard,
} from "../../lib/useUnsavedChangesGuard";

type Status = "open" | "done";
const COLUMNS: { key: Status; label: string }[] = [
  { key: "open", label: "Offen" },
  { key: "done", label: "Erledigt" },
];

export default function BoardPanel() {
  const { blocker, setDirty } = useUnsavedChangesGuard();
  const [tasks, setTasks] = useState<BoardTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<Status | null>(null);
  const [editTarget, setEditTarget] = useState<BoardTask | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BoardTask | null>(null);
  const [dialogBusy, setDialogBusy] = useState(false);
  const [newOpen, setNewOpen] = useState(false);

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

      <div className="grid gap-4 md:grid-cols-2">
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
                <div className="flex items-center gap-2">
                  <p className="text-label font-semibold text-ink">{col.label}</p>
                  {col.key === "open" && (
                    <button
                      type="button"
                      onClick={() => setNewOpen(true)}
                      aria-label="Neue Aufgabe"
                      title="Neue Aufgabe"
                      className="grid h-6 w-6 place-items-center rounded-full border border-line bg-white text-ink transition-colors hover:border-teal hover:text-teal"
                    >
                      <span aria-hidden className="text-[16px] leading-none">+</span>
                    </button>
                  )}
                </div>
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

      <TaskDialog
        open={newOpen}
        task={null}
        onClose={() => setNewOpen(false)}
        onSaved={load}
        onError={setError}
        onDirtyChange={(dirty) => setDirty("new-task", dirty)}
      />

      <TaskDialog
        open={editTarget !== null}
        task={editTarget}
        onClose={() => setEditTarget(null)}
        onSaved={load}
        onError={setError}
        onDirtyChange={(dirty) => setDirty("edit-task", dirty)}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Aufgabe löschen"
        message={deleteTarget ? `„${deleteTarget.title}" wird gelöscht.` : undefined}
        busy={dialogBusy}
        onConfirm={remove}
        onCancel={() => setDeleteTarget(null)}
      />
      <UnsavedChangesDialog blocker={blocker} />
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
      {task.body && <TaskDetails body={task.body} />}
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

function TaskDetails({ body }: { body: string }) {
  const blocks: { type: "list" | "text"; lines: string[] }[] = [];
  for (const line of body.split("\n")) {
    const bullet = /^[-*]\s+(.*)$/.exec(line);
    const type = bullet ? "list" : "text";
    const value = bullet ? bullet[1] : line;
    const last = blocks[blocks.length - 1];
    if (last?.type === type) last.lines.push(value);
    else blocks.push({ type, lines: [value] });
  }
  return (
    <div className="mt-1 space-y-1 text-caption text-muted">
      {blocks.map((block, index) =>
        block.type === "list" ? (
          <ul key={index} className="list-disc space-y-0.5 pl-5">
            {block.lines.map((line, lineIndex) => <li key={lineIndex}>{line}</li>)}
          </ul>
        ) : (
          <p key={index} className="whitespace-pre-wrap">{block.lines.join("\n")}</p>
        )
      )}
    </div>
  );
}

function TaskDialog({
  open,
  task,
  onClose,
  onSaved,
  onError,
  onDirtyChange,
}: {
  open: boolean;
  task: BoardTask | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  onError: (msg: string) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [discardOpen, setDiscardOpen] = useState(false);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const initial = { title: task?.title ?? "", body: task?.body ?? "" };
  const dirty = useFormDirty({ title, body }, initial, open);

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  // Reset the fields each time the mask opens.
  useEffect(() => {
    if (open) {
      setTitle(initial.title);
      setBody(initial.body);
      setTitleError(null);
      setSaveError(null);
    }
  }, [open, initial.body, initial.title]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    if (!title.trim()) {
      setTitleError("Bitte einen Titel eingeben.");
      return;
    }
    setTitleError(null);
    setSaveError(null);
    setBusy(true);
    try {
      if (task) {
        await updateBoardTask(task.id, { title: title.trim(), body });
      } else {
        await createBoardTask(title.trim(), body || undefined);
      }
      onDirtyChange(false);
      await onSaved();
      onClose();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.";
      setSaveError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
    if (event.currentTarget === bodyRef.current && event.shiftKey) return;
    event.preventDefault();
    if (!busy) event.currentTarget.form?.requestSubmit();
  };

  const insertBullet = () => {
    const textarea = bodyRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const lineStart = body.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
    if (/^[-*]\s/.test(body.slice(lineStart))) return;
    const next = `${body.slice(0, lineStart)}- ${body.slice(lineStart)}`;
    setBody(next);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + 2, start + 2);
    });
  };

  const close = () => {
    if (busy) return;
    if (dirty) setDiscardOpen(true);
    else onClose();
  };

  return (
    <>
    <Modal open={open} onClose={close} labelledBy="task-dialog-title">
      <form onSubmit={submit}>
        <h2 id="task-dialog-title" className="text-ui font-semibold text-ink">
          {task ? "Aufgabe bearbeiten" : "Neue Aufgabe"}
        </h2>
        <label htmlFor="new-task-title-input" className="mt-4 block text-label text-ink-soft">Titel</label>
        <Input
          id="new-task-title-input"
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={onKeyDown}
          aria-invalid={Boolean(titleError)}
          placeholder="Titel"
          className="mt-1.5"
        />
        {titleError && <p role="alert" className="mt-1 text-caption text-red-700">{titleError}</p>}
        <label htmlFor="new-task-body" className="mt-3 block text-label text-ink-soft">Details (optional)</label>
        <Textarea
          ref={bodyRef}
          id="new-task-body"
          className="mt-1.5 min-h-[96px] resize-y"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Details (optional)"
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <button type="button" onClick={insertBullet} className="text-caption font-medium text-teal hover:underline">
            Stichpunkt
          </button>
          <p className="text-caption text-muted">Enter zum Speichern · Shift+Enter für neue Zeile</p>
        </div>
        {saveError && <p role="alert" className="mt-2 text-caption text-red-700">{saveError}</p>}
        <div className="mt-5 flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={close} disabled={busy}>
            Abbrechen
          </Button>
          <Button type="submit" disabled={busy || !title.trim()}>
            {busy ? "…" : task ? "Speichern" : "Anlegen"}
          </Button>
        </div>
      </form>
    </Modal>
    <ConfirmDialog
      open={discardOpen}
      title="Aufgabe verwerfen?"
      message="Titel und Details wurden noch nicht gespeichert."
      confirmText="Verwerfen"
      variant="danger"
      onCancel={() => setDiscardOpen(false)}
      onConfirm={() => {
        setDiscardOpen(false);
        onClose();
      }}
    />
    </>
  );
}
