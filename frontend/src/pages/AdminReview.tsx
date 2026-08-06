// Moderation panel (Sprint D): tabs for spot submissions, hero-image candidates,
// reported images, and flagged tips/ratings. Each item shows context + actions,
// and the list refreshes after a decision.

import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { resolveMediaUrl } from "../lib/api";
import {
  ApiError,
  approveImage,
  approveSubmission,
  dismissReports,
  getAdminRegionsFlat,
  getReviewQueue,
  hideRating,
  hideTip,
  restoreRating,
  restoreTip,
  rejectImage,
  rejectSubmission,
  removeImage,
  type Region,
  type ReviewQueue,
  type ReviewSubmission,
  type SubmissionCompletion,
} from "../lib/api";
import { SPORT_LABELS } from "../lib/labels";
import PromptDialog from "../components/ui/PromptDialog";
import { PageHeader, Badge } from "../components/admin/ui";
import { createAdminReturnState } from "../lib/adminNavigation";
import { useUnsavedChangesGuard } from "../lib/useUnsavedChangesGuard";
import UnsavedChangesDialog from "../components/admin/UnsavedChangesDialog";
import DuplicateWarningDialog from "../components/admin/DuplicateWarningDialog";
import {
  parseDuplicateConflict,
  type DuplicateConflict,
} from "../lib/duplicateConflicts";

type Tab = "submissions" | "hero" | "gallery" | "reported" | "content";

const TABS: { key: Tab; label: string; count: (q: ReviewQueue) => number }[] = [
  { key: "submissions", label: "Spot-Einreichungen", count: (q) => q.counts.submissions_pending },
  { key: "hero", label: "Hero-Bilder", count: (q) => q.counts.hero_candidates_pending },
  { key: "gallery", label: "Galeriebilder", count: (q) => q.counts.gallery_images_pending },
  { key: "reported", label: "Gemeldete Bilder", count: (q) => q.counts.reported_images },
  {
    key: "content",
    label: "Tips & Bewertungen",
    count: (q) => q.tips.length + q.ratings.length,
  },
];

export default function AdminReview() {
  const { blocker, setDirty } = useUnsavedChangesGuard();
  const [params, setParams] = useSearchParams();
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const requestedTab = params.get("tab");
  const tab: Tab = TABS.some((item) => item.key === requestedTab)
    ? (requestedTab as Tab)
    : "submissions";
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [duplicateWarning, setDuplicateWarning] = useState<{
    conflict: DuplicateConflict;
    retry: () => void;
  } | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setQueue(await getReviewQueue());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Regions power the completion form's dropdown; load once.
  useEffect(() => {
    getAdminRegionsFlat()
      .then(setRegions)
      .catch(() => {
        /* dropdown just stays empty; approval still works for full payloads */
      });
  }, []);

  const act = async (fn: () => Promise<unknown>, duplicateRetry?: () => void) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      const duplicate = parseDuplicateConflict(e);
      if (duplicate && duplicateRetry) {
        setDuplicateWarning({ conflict: duplicate, retry: duplicateRetry });
        return;
      }
      setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  // Reject/remove actions capture an optional note via a dialog (replaces
  // window.prompt). `run` receives the note (undefined when left blank).
  const [noteAction, setNoteAction] = useState<{
    title: string;
    confirmText: string;
    run: (note?: string) => Promise<unknown>;
  } | null>(null);
  const askNote = (
    title: string,
    confirmText: string,
    run: (note?: string) => Promise<unknown>
  ) => setNoteAction({ title, confirmText, run });

  const selectTab = (nextTab: Tab) => {
    const next = new URLSearchParams(params);
    if (nextTab === "submissions") next.delete("tab");
    else next.set("tab", nextTab);
    setParams(next, { replace: true });
  };

  const approve = (
    submissionId: string,
    completion: SubmissionCompletion,
    allowDuplicate = false
  ) => void act(
    () => approveSubmission(submissionId, {
      ...completion,
      allow_duplicate: allowDuplicate,
    }),
    allowDuplicate
      ? undefined
      : () => approve(submissionId, completion, true)
  );

  return (
    <div>
      <PageHeader
        title="Review"
      />

      {error && (
        <div role="alert" className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-admin-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => selectTab(t.key)}
            className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-ui font-medium transition-colors ${
              tab === t.key
                ? "border-admin-primary text-admin-fg"
                : "border-transparent text-admin-muted hover:text-admin-fg"
            }`}
          >
            {t.label}
            {queue && t.count(queue) > 0 && (
              <Badge tone={tab === t.key ? "primary" : "neutral"} dot={false}>
                {t.count(queue)}
              </Badge>
            )}
          </button>
        ))}
      </div>

      {!queue ? (
        <div className="mt-6 text-ui text-admin-muted">Lädt…</div>
      ) : (
        <div className="mt-6 space-y-3">
          {tab === "submissions" &&
            (queue.submissions.length === 0 ? (
              <Empty>Keine offenen Einreichungen.</Empty>
            ) : (
              queue.submissions.map((s) => (
                <SubmissionCard
                  key={s.id}
                  submission={s}
                  regions={regions}
                  busy={busy}
                  onApprove={(completion) => approve(s.id, completion)}
                  onReject={() =>
                    askNote("Einreichung ablehnen", "Ablehnen", (note) =>
                      rejectSubmission(s.id, note)
                    )
                  }
                />
              ))
            ))}

          {tab === "hero" &&
            (queue.hero_candidates.length === 0 ? (
              <Empty>Keine Hero-Kandidaten.</Empty>
            ) : (
              queue.hero_candidates.map((i) => (
                <Card key={i.id}>
                  <ImagePreview url={i.url} credit={i.credit} spotId={i.spot_id} />
                  <Actions>
                    <Approve busy={busy} onClick={() => act(() => approveImage(i.id))}>
                      Als Hero freigeben
                    </Approve>
                    <Reject
                      busy={busy}
                      onClick={() =>
                        askNote("Bild ablehnen", "Ablehnen", (note) =>
                          rejectImage(i.id, note)
                        )
                      }
                    >
                      Ablehnen
                    </Reject>
                  </Actions>
                </Card>
              ))
            ))}

          {tab === "gallery" &&
            (queue.pending_gallery_images.length === 0 ? (
              <Empty>Keine Galeriebilder zur Prüfung.</Empty>
            ) : (
              queue.pending_gallery_images.map((i) => (
                <Card key={i.id}>
                  <ImagePreview url={i.url} credit={i.credit} spotId={i.spot_id} />
                  <Actions>
                    <Approve busy={busy} onClick={() => act(() => approveImage(i.id))}>
                      Freigeben
                    </Approve>
                    <Reject
                      busy={busy}
                      onClick={() =>
                        askNote("Bild ablehnen", "Ablehnen", (note) =>
                          rejectImage(i.id, note)
                        )
                      }
                    >
                      Ablehnen
                    </Reject>
                  </Actions>
                </Card>
              ))
            ))}

          {tab === "reported" &&
            (queue.reported_images.length === 0 ? (
              <Empty>Keine gemeldeten Bilder.</Empty>
            ) : (
              queue.reported_images.map((i) => (
                <Card key={i.id}>
                  <ImagePreview
                    url={i.url}
                    credit={i.credit}
                    spotId={i.spot_id}
                    badge={`${i.report_count} Meldung(en)`}
                  />
                  <Actions>
                    <Reject
                      busy={busy}
                      onClick={() =>
                        askNote("Bild entfernen", "Entfernen", (note) =>
                          removeImage(i.id, note)
                        )
                      }
                    >
                      Entfernen
                    </Reject>
                    <Neutral busy={busy} onClick={() => act(() => dismissReports(i.id))}>
                      Meldungen verwerfen
                    </Neutral>
                  </Actions>
                </Card>
              ))
            ))}

          {tab === "content" &&
            (queue.tips.length === 0 && queue.ratings.length === 0 ? (
              <Empty>Keine Tips oder Bewertungen.</Empty>
            ) : (
              <>
                <p className="text-label text-muted">
                  Alle veröffentlichten Beiträge (gemeldete zuerst). „Verbergen"
                  nimmt einen Beitrag aus der öffentlichen Liste — reversibel.
                </p>
                {queue.ratings.map((r) => (
                  <Card key={r.id}>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-label text-admin-muted">
                        <span>Bewertung · {r.stars}★ · {r.author_name}</span>
                        {r.flagged && <Badge tone="warning">gemeldet</Badge>}
                      </div>
                      <p className="mt-1 text-ui text-admin-fg">{r.conditions}</p>
                    </div>
                    <Actions>
                      {r.status === "hidden" ? (
                        <Neutral busy={busy} onClick={() => act(() => restoreRating(r.id))}>
                          Wiederherstellen
                        </Neutral>
                      ) : (
                        <Reject busy={busy} onClick={() => act(() => hideRating(r.id))}>
                          Verbergen
                        </Reject>
                      )}
                    </Actions>
                  </Card>
                ))}
                {queue.tips.map((t) => (
                  <Card key={t.id}>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-label text-admin-muted">
                        <span>Tipp · {t.author_name}</span>
                        {t.flagged && <Badge tone="warning">gemeldet</Badge>}
                      </div>
                      <p className="mt-1 text-ui text-admin-fg">{t.body}</p>
                    </div>
                    <Actions>
                      {t.status === "hidden" ? (
                        <Neutral busy={busy} onClick={() => act(() => restoreTip(t.id))}>
                          Wiederherstellen
                        </Neutral>
                      ) : (
                        <Reject busy={busy} onClick={() => act(() => hideTip(t.id))}>
                          Verbergen
                        </Reject>
                      )}
                    </Actions>
                  </Card>
                ))}
              </>
            ))}
        </div>
      )}

      <PromptDialog
        open={noteAction !== null}
        title={noteAction?.title ?? ""}
        label="Notiz (optional)"
        confirmText={noteAction?.confirmText ?? "Bestätigen"}
        allowEmpty
        busy={busy}
        onConfirm={(note) => {
          const action = noteAction;
          setNoteAction(null);
          if (action) void act(() => action.run(note.trim() || undefined));
        }}
        onCancel={() => setNoteAction(null)}
        onDirtyChange={(dirty) => setDirty("review-note", dirty)}
      />
      <UnsavedChangesDialog blocker={blocker} />
      <DuplicateWarningDialog
        conflict={duplicateWarning?.conflict ?? null}
        busy={busy}
        onClose={() => setDuplicateWarning(null)}
        onOverride={() => {
          const retry = duplicateWarning?.retry;
          setDuplicateWarning(null);
          retry?.();
        }}
      />
    </div>
  );
}

const SPORT_KEYS = Object.keys(SPORT_LABELS);

/**
 * One pending spot proposal. A full community submission already carries
 * region + coordinates and approves in one click. A name-only account proposal
 * does not — so the admin completes region, coordinates (and optionally sports)
 * inline before it can become a draft spot. The finer details are refined later
 * on the spot's edit page.
 */
function SubmissionCard({
  submission,
  regions,
  busy,
  onApprove,
  onReject,
}: {
  submission: ReviewSubmission;
  regions: Region[];
  busy: boolean;
  onApprove: (completion: SubmissionCompletion) => void;
  onReject: () => void;
}) {
  const p = submission.payload;
  const hasRegion = typeof p.region_id === "string";
  const hasLat = typeof p.lat === "number";
  const hasLon = typeof p.lon === "number";
  const complete = hasRegion && hasLat && hasLon;

  const [regionId, setRegionId] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [sports, setSports] = useState<string[]>([]);

  const latN = Number(lat);
  const lonN = Number(lon);
  const latOk = lat.trim() !== "" && Number.isFinite(latN) && latN >= -90 && latN <= 90;
  const lonOk = lon.trim() !== "" && Number.isFinite(lonN) && lonN >= -180 && lonN <= 180;
  const canComplete = regionId !== "" && latOk && lonOk;

  const toggleSport = (k: string) =>
    setSports((cur) => (cur.includes(k) ? cur.filter((s) => s !== k) : [...cur, k]));

  return (
    <Card>
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-ink">{submission.name ?? "—"}</div>
        <div className="text-label text-muted">
          von {submission.submitter_name} ·{" "}
          {new Date(submission.created_at).toLocaleDateString("de-DE")}
        </div>

        {complete ? (
          <pre className="admin-mono mt-2 max-h-40 overflow-auto rounded-md border border-admin-border bg-admin-hover p-2.5 text-caption text-admin-fg2">
            {JSON.stringify(submission.payload, null, 2)}
          </pre>
        ) : (
          <div className="mt-3 rounded-md border border-admin-border bg-admin-hover p-3">
            <p className="mb-2 text-caption font-medium text-muted">
              Nur als Name eingereicht — zum Anlegen Region und Koordinaten ergänzen.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-caption text-muted">Region</span>
                <select
                  value={regionId}
                  onChange={(e) => setRegionId(e.target.value)}
                  className="w-full rounded-lg border border-line bg-white px-2 py-1.5 text-label text-ink"
                >
                  <option value="">— wählen —</option>
                  {regions.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                      {r.country ? `, ${r.country}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="mb-1 block text-caption text-muted">Breitengrad</span>
                  <input
                    inputMode="decimal"
                    value={lat}
                    onChange={(e) => setLat(e.target.value)}
                    placeholder="54.41"
                    className={`w-full rounded-lg border bg-white px-2 py-1.5 text-label text-ink ${
                      lat && !latOk ? "border-red-300" : "border-line"
                    }`}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-caption text-muted">Längengrad</span>
                  <input
                    inputMode="decimal"
                    value={lon}
                    onChange={(e) => setLon(e.target.value)}
                    placeholder="10.22"
                    className={`w-full rounded-lg border bg-white px-2 py-1.5 text-label text-ink ${
                      lon && !lonOk ? "border-red-300" : "border-line"
                    }`}
                  />
                </label>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {SPORT_KEYS.map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => toggleSport(k)}
                  aria-pressed={sports.includes(k)}
                  className={`rounded-2xl px-2.5 py-1 text-caption font-medium ${
                    sports.includes(k)
                      ? "bg-teal text-white"
                      : "bg-white text-muted ring-1 ring-line hover:text-teal"
                  }`}
                >
                  {SPORT_LABELS[k]}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
      <Actions>
        {complete ? (
          <Approve busy={busy} onClick={() => onApprove({})}>
            Als Entwurf anlegen
          </Approve>
        ) : (
          <Approve
            busy={busy || !canComplete}
            onClick={() =>
              onApprove({
                region_id: regionId,
                lat: latN,
                lon: lonN,
                sports: sports.length ? sports : undefined,
              })
            }
          >
            Vervollständigen & anlegen
          </Approve>
        )}
        <Reject busy={busy} onClick={onReject}>
          Ablehnen
        </Reject>
      </Actions>
    </Card>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 rounded-lg border border-admin-border bg-admin-surface p-4">
      {children}
    </div>
  );
}
function Actions({ children }: { children: React.ReactNode }) {
  return <div className="flex shrink-0 flex-wrap gap-2">{children}</div>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-admin-border bg-admin-surface p-10 text-center text-ui text-admin-muted">{children}</div>;
}
function Approve({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" disabled={busy} onClick={onClick} className="rounded-md bg-admin-primary px-3 py-1.5 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50">
      {children}
    </button>
  );
}
function Reject({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" disabled={busy} onClick={onClick} className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-1.5 text-label font-medium text-admin-danger transition-colors hover:brightness-95 disabled:opacity-50">
      {children}
    </button>
  );
}
function Neutral({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" disabled={busy} onClick={onClick} className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50">
      {children}
    </button>
  );
}
function ImagePreview({
  url,
  credit,
  spotId,
  badge,
}: {
  url: string;
  credit: string | null;
  spotId: string;
  badge?: string;
}) {
  const location = useLocation();
  const editorState = createAdminReturnState(location, "Review");
  return (
    <div className="flex min-w-0 items-start gap-3">
      <img
        src={resolveMediaUrl(url)}
        alt=""
        className="h-20 w-32 shrink-0 rounded-lg object-cover"
      />
      <div className="min-w-0 text-label">
        {credit && <div className="text-ink">Credit: {credit}</div>}
        {badge && <div className="font-medium text-ink">{badge}</div>}
        <Link
          to={`/admin/spot/${spotId}/edit`}
          state={editorState}
          className="text-muted hover:underline"
        >
          Zum Spot
        </Link>
      </div>
    </div>
  );
}
