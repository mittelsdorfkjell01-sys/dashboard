import { useEffect, useState, type FormEvent } from "react";
import {
  listMySubmissions,
  addSubmission,
  SUBMISSIONS_EVENT,
  AccountError,
  type MySubmission,
  type SubmissionStatus,
} from "../../lib/account";
import { Button, Input } from "../../components/ui";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { PlusCircleIcon } from "../../lib/icons";
import { useFormDirty } from "../../lib/useUnsavedChangesGuard";

type Badge = { label: string; cls: string };

// Keyed by the raw backend status. `merged` = the proposal was accepted and a
// (still draft) spot was created — hence "Übernommen", not "Veröffentlicht"
// (go-live is a separate step). Looked up defensively (see FALLBACK) so an
// unrecognised status renders a neutral badge instead of crashing the page.
const STATUS: Record<SubmissionStatus, Badge> = {
  pending: {
    label: "In Prüfung",
    cls: "bg-amber-100 text-amber-800",
  },
  merged: {
    label: "Übernommen",
    cls: "bg-success-bg text-success",
  },
  rejected: {
    label: "Abgelehnt",
    cls: "bg-danger-bg text-danger",
  },
};

const FALLBACK: Badge = { label: "Unbekannt", cls: "bg-line text-muted" };

export default function MeineSpots() {
  const [subs, setSubs] = useState<MySubmission[]>(listMySubmissions);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const dirty = useFormDirty(name, "", open);

  useEffect(() => {
    const refresh = () => setSubs(listMySubmissions());
    window.addEventListener(SUBMISSIONS_EVENT, refresh);
    return () => window.removeEventListener(SUBMISSIONS_EVENT, refresh);
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    setBusy(true);
    try {
      await addSubmission(name);
      setName("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Einreichen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>
          <PlusCircleIcon className="text-sz-18" /> Spot vorschlagen
        </Button>
      </div>
      <Modal
        open={open}
        onClose={() => dirty ? setConfirmDiscard(true) : setOpen(false)}
        labelledBy="suggest-spot-title"
      >
        <form onSubmit={onSubmit} className="space-y-4">
          <h2 id="suggest-spot-title" className="text-sz-18 font-semibold text-ink">
            Spot vorschlagen
          </h2>
          <div>
            <label htmlFor="suggest-spot-name" className="text-label font-medium text-ink">
              Name des Spots
            </label>
          <Input
            id="suggest-spot-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name des Spots, z. B. „Fehmarn Wulfener Hals“"
            className="mt-1 w-full"
          />
            <p className="mt-1 text-caption text-muted">
              Der Vorschlag wird vor einer Veröffentlichung redaktionell geprüft.
            </p>
          </div>
          {error && <p role="alert" className="text-label font-medium text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => dirty ? setConfirmDiscard(true) : setOpen(false)}
              disabled={busy}
            >
              Abbrechen
            </Button>
            <Button type="submit" disabled={busy || !name.trim()}>
              {busy ? "Sende …" : "Einreichen"}
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={confirmDiscard}
        title="Eingabe verwerfen?"
        message="Der noch nicht eingereichte Spotname geht verloren."
        confirmText="Verwerfen"
        onCancel={() => setConfirmDiscard(false)}
        onConfirm={() => {
          setConfirmDiscard(false);
          setName("");
          setOpen(false);
        }}
      />

      {subs.length === 0 ? (
        <p className="rounded-[14px] border border-dashed border-line px-6 py-10 text-center text-ui text-muted">
          Du hast noch keine Spots eingereicht.
        </p>
      ) : (
        <ul className="space-y-2">
          {subs.map((s) => {
            const st = STATUS[s.status] ?? FALLBACK;
            return (
              <li
                key={s.id}
                className="flex items-center justify-between gap-3 rounded-[14px] border border-line bg-surface p-4"
              >
                <span className="min-w-0">
                  <span className="block truncate text-body font-medium text-ink">
                    {s.name}
                  </span>
                  <span className="block text-caption text-muted">
                    Eingereicht am{" "}
                    {new Date(s.createdAt).toLocaleDateString("de-DE", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </span>
                </span>
                <span
                  className={`shrink-0 rounded-[14px] px-2.5 py-1 text-sz-11 font-semibold ${st.cls}`}
                >
                  {st.label}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
