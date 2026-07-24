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
import { PlusCircleIcon } from "../../lib/icons";

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
    cls: "bg-green-100 text-green-800",
  },
  rejected: {
    label: "Abgelehnt",
    cls: "bg-red-100 text-red-700",
  },
};

const FALLBACK: Badge = { label: "Unbekannt", cls: "bg-line text-muted" };

export default function MeineSpots() {
  const [subs, setSubs] = useState<MySubmission[]>(listMySubmissions);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Einreichen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <form
        onSubmit={onSubmit}
        className="rounded-2xl bg-white p-5 shadow-card"
      >
        <h2 className="flex items-center gap-2 text-[16px] font-semibold text-ink">
          <PlusCircleIcon className="text-[18px] text-teal" />
          Spot vorschlagen
        </h2>
        <p className="mt-1 text-[13px] text-muted">
          Reiche einen neuen Spot ein — nach Prüfung erscheint er öffentlich.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name des Spots, z. B. „Fehmarn Wulfener Hals“"
            className="flex-1"
            aria-label="Spot-Name"
          />
          <Button type="submit" disabled={busy || !name.trim()}>
            {busy ? "Sende …" : "Einreichen"}
          </Button>
        </div>
        {error && (
          <p role="alert" className="mt-2 text-[13px] font-medium text-red-600">
            {error}
          </p>
        )}
      </form>

      {subs.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line px-6 py-10 text-center text-[14px] text-muted">
          Du hast noch keine Spots eingereicht.
        </p>
      ) : (
        <ul className="space-y-2">
          {subs.map((s) => {
            const st = STATUS[s.status] ?? FALLBACK;
            return (
              <li
                key={s.id}
                className="flex items-center justify-between gap-3 rounded-2xl bg-white p-4 shadow-card"
              >
                <span className="min-w-0">
                  <span className="block truncate text-[15px] font-medium text-ink">
                    {s.name}
                  </span>
                  <span className="block text-[12px] text-muted">
                    Eingereicht am{" "}
                    {new Date(s.createdAt).toLocaleDateString("de-DE", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </span>
                </span>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${st.cls}`}
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
