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
import { Field, Input, Select, Textarea } from "../ui";
import { Button } from "./ui";
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
  const [newOpen, setNewOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const boardRef = useRef<HTMLDivElement>(null);

  const load = () =>
    getBoardTasks()
      .then(setTasks)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Board laden fehlgeschlagen.")
      );
  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "x") return;
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return;
      if (!boardRef.current) return;
      event.preventDefault();
      setNewOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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

  const remove = async (ids: string[]) => {
    if (!ids.length || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      const results = await Promise.allSettled(ids.map(deleteBoardTask));
      const failed = results.filter((result) => result.status === "rejected").length;
      const deleted = ids.filter((_, index) => results[index].status === "fulfilled");
      setTasks((current) => current.filter((task) => !deleted.includes(task.id)));
      setSelected((current) => new Set([...current].filter((id) => !deleted.includes(id))));
      if (failed) setError(`${deleted.length} gelöscht, ${failed} konnten nicht gelöscht werden.`);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div ref={boardRef}>
      {error && (
        <div role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700">
          {error}
        </div>
      )}

      <div className="mb-3 flex min-h-9 flex-wrap items-center gap-3">
        {tasks.length > 0 && (
          <label className="flex min-h-9 cursor-pointer items-center gap-2 text-caption text-muted">
            <input
              type="checkbox"
              checked={selected.size === tasks.length}
              onChange={() => setSelected(selected.size === tasks.length ? new Set() : new Set(tasks.map((task) => task.id)))}
              aria-label="Alle Aufgaben auswählen"
              className="h-4 w-4 rounded border-line accent-[var(--a-primary)]"
            />
            Alle auswählen
          </label>
        )}
        {selected.size > 0 && (
          <Button type="button" variant="destructive" disabled={deleting} onClick={() => void remove([...selected])}>
            {deleting ? "Löschen …" : `${selected.size} ausgewählte löschen`}
          </Button>
        )}
        <Button type="button" variant="primary" onClick={() => setNewOpen(true)} className="ml-auto">
          Neue Aufgabe
        </Button>
      </div>

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
                      selected={selected.has(t.id)}
                      onSelect={() => setSelected((current) => {
                        const next = new Set(current);
                        if (next.has(t.id)) next.delete(t.id); else next.add(t.id);
                        return next;
                      })}
                      onDelete={() => void remove([t.id])}
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
      <UnsavedChangesDialog blocker={blocker} />
    </div>
  );
}

function TaskCard({
  task,
  onMove,
  onEdit,
  selected,
  onSelect,
  onDelete,
}: {
  task: BoardTask;
  onMove: (status: Status) => void;
  onEdit: () => void;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", task.id)}
      onClick={onEdit}
      className={`cursor-pointer rounded-lg border bg-white p-3 active:cursor-grabbing ${selected ? "border-teal ring-1 ring-teal/30" : "border-line"}`}
    >
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={selected}
          onChange={onSelect}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Aufgabe ${task.title} auswählen`}
          className="mt-0.5 h-4 w-4 rounded border-line accent-[var(--a-primary)]"
        />
        <p className="min-w-0 flex-1 text-label font-medium text-ink">{task.title}</p>
      </div>
      {task.body && <TaskDetails body={task.body} />}
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-caption text-muted">{task.author ?? "—"}</span>
        <div className="flex items-center gap-2 text-caption">
          {task.status === "open" ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onMove("done");
              }}
              className="font-medium text-teal hover:underline"
            >
              → Erledigt
            </button>
          ) : (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onMove("open");
              }}
              className="font-medium text-teal hover:underline"
            >
              ← Offen
            </button>
          )}
          <button type="button" onClick={onEdit} className="text-muted hover:text-ink">
            Bearbeiten
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="text-muted hover:text-admin-danger"
          >
            Löschen
          </button>
        </div>
      </div>
    </div>
  );
}

function TaskDetails({ body }: { body: string }) {
  const blocks: { type: "bullet" | "number" | "text"; lines: string[] }[] = [];
  for (const line of body.split("\n")) {
    const bullet = /^[-*]\s+(.*)$/.exec(line);
    const numbered = /^\d+\.\s+(.*)$/.exec(line);
    const type = bullet ? "bullet" : numbered ? "number" : "text";
    const value = bullet?.[1] ?? numbered?.[1] ?? line;
    const last = blocks[blocks.length - 1];
    if (last?.type === type) last.lines.push(value);
    else blocks.push({ type, lines: [value] });
  }
  return (
    <div className="mt-1 space-y-1 text-caption text-muted">
      {blocks.map((block, index) =>
        block.type === "bullet" ? (
          <ul key={index} className="list-disc space-y-0.5 pl-5">
            {block.lines.map((line, lineIndex) => <li key={lineIndex}>{line}</li>)}
          </ul>
        ) : block.type === "number" ? (
          <ol key={index} className="list-decimal space-y-0.5 pl-5">
            {block.lines.map((line, lineIndex) => <li key={lineIndex}>{line}</li>)}
          </ol>
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
  const [status, setStatus] = useState<Status>("open");
  const [busy, setBusy] = useState(false);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [discardOpen, setDiscardOpen] = useState(false);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const initial = { title: task?.title ?? "", body: task?.body ?? "", status: task?.status ?? "open" as Status };
  const dirty = useFormDirty({ title, body, status }, initial, open);

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  // Reset the fields each time the mask opens.
  useEffect(() => {
    if (open) {
      setTitle(initial.title);
      setBody(initial.body);
      setStatus(initial.status);
      setTitleError(null);
      setSaveError(null);
    }
  }, [open, initial.body, initial.status, initial.title]);

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
        await updateBoardTask(task.id, { title: title.trim(), body, status });
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

  const onTitleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (!busy) event.currentTarget.form?.requestSubmit();
    }
  };

  const onBodyKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" && event.key !== "Backspace") return;
    const textarea = event.currentTarget;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    if (start !== end) return;
    const lineStart = body.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
    const lineEndIndex = body.indexOf("\n", start);
    const lineEnd = lineEndIndex === -1 ? body.length : lineEndIndex;
    const line = body.slice(lineStart, lineEnd);
    const marker = /^(\s*)([-*]|(\d+)\.)\s(.*)$/.exec(line);
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!busy) textarea.form?.requestSubmit();
      return;
    }
    if (!marker) return;
    const prefixLength = marker[1].length + marker[2].length + 1;
    if (event.key === "Backspace" && marker[4] === "" && start === lineStart + prefixLength) {
      event.preventDefault();
      const next = body.slice(0, lineStart) + body.slice(lineStart + prefixLength);
      setBody(next);
      requestAnimationFrame(() => textarea.setSelectionRange(lineStart, lineStart));
      return;
    }
    if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      const nextPrefix = marker[3] ? `${Number(marker[3]) + 1}. ` : "- ";
      if (marker[4] === "") {
        const next = body.slice(0, lineStart) + body.slice(lineEnd);
        setBody(next);
        requestAnimationFrame(() => textarea.setSelectionRange(lineStart, lineStart));
      } else {
        const insertion = `\n${marker[1]}${nextPrefix}`;
        const next = body.slice(0, start) + insertion + body.slice(start);
        setBody(next);
        requestAnimationFrame(() => textarea.setSelectionRange(start + insertion.length, start + insertion.length));
      }
    }
  };

  const close = () => {
    if (busy) return;
    if (dirty) setDiscardOpen(true);
    else onClose();
  };

  return (
    <>
    <Modal open={open} onClose={close} labelledBy="task-dialog-title" cardClassName="max-w-2xl rounded-xl bg-white p-0">
      <form onSubmit={submit} className="overflow-hidden">
        <div className="border-b border-line px-5 py-4">
        <h2 id="task-dialog-title" className="text-ui font-semibold text-ink">
          {task ? "Aufgabe bearbeiten" : "Neue Aufgabe"}
        </h2>
        </div>
        <div className="space-y-4 px-5 py-5">
        <Field label="Titel" required error={titleError ?? undefined}>
        <Input
          id="new-task-title-input"
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={onTitleKeyDown}
          aria-invalid={Boolean(titleError)}
          placeholder="Titel"
        />
        </Field>
        {task && <Field label="Status"><Select value={status} onChange={(event) => setStatus(event.target.value as Status)}><option value="open">Offen</option><option value="done">Erledigt</option></Select></Field>}
        <Field label="Beschreibung">
        <Textarea
          ref={bodyRef}
          id="new-task-body"
          className="min-h-[180px] resize-y font-mono text-[13px] leading-6"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={onBodyKeyDown}
          placeholder="Beschreibung hinzufügen …"
        />
        </Field>
        {saveError && <p role="alert" className="mt-2 text-caption text-red-700">{saveError}</p>}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-line bg-band/40 px-5 py-3">
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
