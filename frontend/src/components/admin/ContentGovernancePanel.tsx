import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  createSpotContentSource,
  deleteSpotContentSource,
  getAdminSpot,
  getSpotContentSources,
  setSpotContentReview,
  updateSpotContentSource,
  type ContentReviewStatus,
  type ContentSourceStatus,
  type SpotContentSource,
  type SpotRead,
} from "../../lib/api";
import { LinkIcon, TrashIcon } from "../../lib/icons";
import { gapLabel } from "../../lib/labels";
import { Button, Input, Select, Textarea } from "./ui";

const FIELD_OPTIONS = [
  ["location", "Standort / Koordinaten"],
  ["sports", "Sportarten"],
  ["level", "Niveau"],
  ["editorial.description", "Beschreibung"],
  ["editorial.safety_notice", "Sicherheitshinweis"],
] as const;

const REVIEW_LABELS: Record<ContentReviewStatus, string> = {
  unreviewed: "Ungeprüft",
  in_review: "In Prüfung",
  verified: "Redaktionell geprüft",
  review_due: "Erneute Prüfung fällig",
  conflict: "Widerspruch offen",
};

const SOURCE_LABELS: Record<ContentSourceStatus, string> = {
  unreviewed: "Ungeprüft",
  verified: "Geprüft",
  rejected: "Verworfen",
  conflict: "Widersprüchlich",
};

const today = () => new Date().toISOString().slice(0, 10);
const checkedAt = (date: string) => `${date}T12:00:00.000Z`;
const dateOnly = (value: string) => value.slice(0, 10);
const formatDate = (value?: string | null) =>
  value
    ? new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(new Date(value))
    : "Noch nicht geprüft";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    const detail = error.detail as { message?: string; gaps?: string[] } | undefined;
    if (detail?.gaps?.length) {
      return `${detail.message ?? "Prüfung nicht möglich"} Es fehlen: ${detail.gaps
        .map(gapLabel)
        .join(", ")}.`;
    }
  }
  return error instanceof ApiError
    ? error.message
    : "Die Inhaltsprüfung konnte nicht gespeichert werden.";
}

function SourceRow({
  source,
  spotId,
  onChanged,
}: {
  source: SpotContentSource;
  spotId: string;
  onChanged: () => Promise<void>;
}) {
  const [status, setStatus] = useState<ContentSourceStatus>(source.verification_status);
  const [date, setDate] = useState(dateOnly(source.checked_at));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await updateSpotContentSource(spotId, source.id, {
        verification_status: status,
        checked_at: checkedAt(date),
        expected_updated_at: source.updated_at,
      });
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Quelle „${source.title}“ wirklich entfernen?`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteSpotContentSource(spotId, source.id);
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <li className="border-t border-admin-border py-4 first:border-t-0 first:pt-0 last:pb-0">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-ui font-medium text-admin-fg">
            {FIELD_OPTIONS.find(([value]) => value === source.field_path)?.[1] ?? source.field_path}
          </p>
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-flex max-w-full items-center gap-1 text-ui text-admin-primary underline underline-offset-2"
          >
            <LinkIcon aria-hidden className="shrink-0 text-sz-16" />
            <span className="truncate">{source.title}</span>
          </a>
          <p className="mt-1 break-words text-caption text-admin-muted">
            {[source.publisher, `zuletzt geprüft ${formatDate(source.checked_at)}`]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {source.note && <p className="mt-2 text-caption text-admin-fg2">{source.note}</p>}
        </div>
        <button
          type="button"
          aria-label={`Quelle ${source.title} entfernen`}
          title="Quelle entfernen"
          disabled={busy}
          onClick={() => void remove()}
          className="grid min-h-11 min-w-11 shrink-0 place-items-center rounded-md text-admin-muted transition-colors hover:bg-admin-danger-bg hover:text-admin-danger disabled:opacity-50"
        >
          <TrashIcon aria-hidden className="text-sz-18" />
        </button>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
        <label className="min-w-0 text-caption font-medium text-admin-fg2">
          Quellenstatus
          <Select
            className="mt-1 min-h-11 w-full"
            value={status}
            onChange={(event) => setStatus(event.target.value as ContentSourceStatus)}
          >
            {Object.entries(SOURCE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
        </label>
        <label className="min-w-0 text-caption font-medium text-admin-fg2">
          Geprüft am
          <Input
            type="date"
            className="mt-1 min-h-11"
            max={today()}
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <Button
          className="min-h-11"
          disabled={busy || !date || (status === source.verification_status && date === dateOnly(source.checked_at))}
          onClick={() => void save()}
        >
          {busy ? "Speichern …" : "Status speichern"}
        </Button>
      </div>
      {error && <p role="alert" className="mt-2 text-caption font-medium text-admin-danger">{error}</p>}
    </li>
  );
}

export default function ContentGovernancePanel({
  spotId,
  onSpotChanged,
}: {
  spotId: string;
  onSpotChanged?: (spot: SpotRead) => void;
}) {
  const [spot, setSpot] = useState<SpotRead | null>(null);
  const [sources, setSources] = useState<SpotContentSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [fieldPath, setFieldPath] = useState(FIELD_OPTIONS[0][0] as string);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [publisher, setPublisher] = useState("");
  const [date, setDate] = useState(today());
  const [note, setNote] = useState("");

  const refresh = useCallback(async () => {
    const [nextSpot, nextSources] = await Promise.all([
      getAdminSpot(spotId),
      getSpotContentSources(spotId),
    ]);
    setSpot(nextSpot);
    setSources(nextSources);
    onSpotChanged?.(nextSpot);
  }, [onSpotChanged, spotId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([getAdminSpot(spotId), getSpotContentSources(spotId)])
      .then(([nextSpot, nextSources]) => {
        if (!active) return;
        setSpot(nextSpot);
        setSources(nextSources);
      })
      .catch((err) => active && setError(errorMessage(err)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [spotId]);

  const addSource = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await createSpotContentSource(spotId, {
        field_path: fieldPath,
        url: url.trim(),
        title: title.trim(),
        publisher: publisher.trim() || null,
        checked_at: checkedAt(date),
        verification_status: "unreviewed",
        note: note.trim() || null,
      });
      setUrl("");
      setTitle("");
      setPublisher("");
      setNote("");
      setDate(today());
      setShowForm(false);
      await refresh();
      setNotice("Quelle gespeichert. Prüfe sie anschließend fachlich und setze ihren Status.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const changeReview = async (status: ContentReviewStatus) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const nextSpot = await setSpotContentReview(spotId, status, spot?.updated_at);
      setSpot(nextSpot);
      onSpotChanged?.(nextSpot);
      setNotice(
        status === "verified"
          ? "Inhalt redaktionell geprüft. Die Prüfung gilt ein Jahr und wird bei Inhaltsänderungen fällig."
          : `Prüfstatus auf „${REVIEW_LABELS[status]}“ gesetzt.`,
      );
    } catch (err) {
      setError(errorMessage(err));
      await refresh().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <p role="status" className="text-ui text-admin-muted">Quellen und Prüfstatus werden geladen …</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-ui font-semibold text-admin-fg">
            {spot ? REVIEW_LABELS[spot.content_status ?? "unreviewed"] : "Prüfstatus unbekannt"}
          </p>
          <p className="mt-1 max-w-[70ch] text-caption text-admin-muted">
            Quellen werden je Inhaltsfeld geprüft. „Redaktionell geprüft“ ist erst möglich,
            wenn alle Pflichtangaben belegt und das Titelbild lizenziert sind.
          </p>
          {spot?.content_reviewed_at && (
            <p className="mt-1 text-caption text-admin-fg2">
              Geprüft {formatDate(spot.content_reviewed_at)} · nächste Prüfung {formatDate(spot.content_review_due_at)}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {spot?.content_status !== "in_review" && (
            <Button className="min-h-11" disabled={busy} onClick={() => void changeReview("in_review")}>
              Prüfung starten
            </Button>
          )}
          <Button
            variant="primary"
            className="min-h-11"
            disabled={busy || spot?.content_status === "verified"}
            onClick={() => void changeReview("verified")}
          >
            {busy ? "Prüfen …" : "Als geprüft bestätigen"}
          </Button>
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2.5">
          <p className="text-ui font-medium text-admin-danger">{error}</p>
          <button type="button" className="mt-2 min-h-11 text-ui font-medium text-admin-danger underline underline-offset-2" onClick={() => void refresh()}>
            Daten erneut laden
          </button>
        </div>
      )}
      {notice && <p role="status" className="text-ui font-medium text-admin-success">{notice}</p>}

      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-ui font-medium text-admin-fg">Feldbezogene Quellen</p>
            <p className="mt-0.5 text-caption text-admin-muted">{sources.length} Quelle{sources.length === 1 ? "" : "n"} hinterlegt</p>
          </div>
          <Button className="min-h-11" onClick={() => setShowForm((value) => !value)}>
            {showForm ? "Formular schließen" : "Quelle hinzufügen"}
          </Button>
        </div>

        {showForm && (
          <div className="mt-4 border-y border-admin-border bg-admin-bg px-3 py-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-ui font-medium text-admin-fg">
                Belegtes Feld
                <Select className="mt-1.5 min-h-11 w-full" value={fieldPath} onChange={(event) => setFieldPath(event.target.value)}>
                  {FIELD_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </Select>
              </label>
              <label className="text-ui font-medium text-admin-fg">
                Geprüft am
                <Input className="mt-1.5 min-h-11" type="date" max={today()} value={date} onChange={(event) => setDate(event.target.value)} />
              </label>
              <label className="text-ui font-medium text-admin-fg sm:col-span-2">
                Quellen-URL
                <Input className="mt-1.5 min-h-11" type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://…" />
              </label>
              <label className="text-ui font-medium text-admin-fg">
                Titel
                <Input className="mt-1.5 min-h-11" required maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} />
              </label>
              <label className="text-ui font-medium text-admin-fg">
                Herausgeber
                <Input className="mt-1.5 min-h-11" maxLength={200} value={publisher} onChange={(event) => setPublisher(event.target.value)} />
              </label>
              <label className="text-ui font-medium text-admin-fg sm:col-span-2">
                Prüfnotiz (optional)
                <Textarea className="mt-1.5 min-h-24 resize-y" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="primary" className="min-h-11" disabled={busy || !url.trim() || !title.trim() || !date} onClick={() => void addSource()}>
                {busy ? "Speichern …" : "Quelle speichern"}
              </Button>
              <Button className="min-h-11" disabled={busy} onClick={() => setShowForm(false)}>Abbrechen</Button>
            </div>
          </div>
        )}

        {sources.length > 0 ? (
          <ul className="mt-4">
            {sources.map((source) => (
              <SourceRow key={source.id} source={source} spotId={spotId} onChanged={refresh} />
            ))}
          </ul>
        ) : (
          <div className="mt-4 rounded-md border border-dashed border-admin-border-strong px-4 py-5">
            <p className="text-ui font-medium text-admin-fg">Noch keine Quelle hinterlegt</p>
            <p className="mt-1 text-caption text-admin-muted">
              Beginne mit Standort, Sportarten, Niveau, Beschreibung und Sicherheitshinweis.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
