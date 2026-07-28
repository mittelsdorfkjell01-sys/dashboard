// Moderation panel (Sprint D): tabs for spot submissions, hero-image candidates,
// reported images, and flagged tips/ratings. Each item shows context + actions,
// and the list refreshes after a decision.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { resolveMediaUrl } from "../lib/api";
import {
  ApiError,
  approveImage,
  approveSubmission,
  dismissReports,
  getRegions,
  getReviewQueue,
  hideRating,
  hideTip,
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
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [tab, setTab] = useState<Tab>("submissions");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
    getRegions()
      .then(setRegions)
      .catch(() => {
        /* dropdown just stays empty; approval still works for full payloads */
      });
  }, []);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
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

  return (
    <div>
      <h1 className="text-[24px] font-semibold text-ink">Review</h1>
      <p className="mt-1 text-[14px] text-muted">
        Nutzer-Beiträge sichten und entscheiden. Jede Aktion wird protokolliert.
      </p>

      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-[13px] font-medium text-red-700">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="mt-5 flex flex-wrap gap-2 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-[14px] font-medium ${
              tab === t.key
                ? "border-teal text-teal"
                : "border-transparent text-muted hover:text-teal"
            }`}
          >
            {t.label}
            {queue && t.count(queue) > 0 && (
              <span className="ml-2 rounded-2xl bg-orange/15 px-2 py-0.5 text-[11px] font-semibold text-ink">
                {t.count(queue)}
              </span>
            )}
          </button>
        ))}
      </div>

      {!queue ? (
        <div className="mt-6 text-[14px] text-muted">Lädt…</div>
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
                  onApprove={(completion) => act(() => approveSubmission(s.id, completion))}
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
                <p className="text-[13px] text-muted">
                  Alle veröffentlichten Beiträge (gemeldete zuerst). „Verbergen"
                  nimmt einen Beitrag aus der öffentlichen Liste — reversibel.
                </p>
                {queue.ratings.map((r) => (
                  <Card key={r.id}>
                    <div className="min-w-0">
                      <div className="text-[13px] text-muted">
                        Bewertung · {r.stars}★ · {r.author_name}
                        {r.flagged && (
                          <span className="ml-2 rounded-2xl bg-orange/15 px-2 py-0.5 text-[11px] font-semibold text-ink">
                            gemeldet
                          </span>
                        )}
                      </div>
                      <p className="text-[14px] text-ink">{r.conditions}</p>
                    </div>
                    <Actions>
                      <Reject busy={busy} onClick={() => act(() => hideRating(r.id))}>
                        Verbergen
                      </Reject>
                    </Actions>
                  </Card>
                ))}
                {queue.tips.map((t) => (
                  <Card key={t.id}>
                    <div className="min-w-0">
                      <div className="text-[13px] text-muted">
                        Tipp · {t.author_name}
                        {t.flagged && (
                          <span className="ml-2 rounded-2xl bg-orange/15 px-2 py-0.5 text-[11px] font-semibold text-ink">
                            gemeldet
                          </span>
                        )}
                      </div>
                      <p className="text-[14px] text-ink">{t.body}</p>
                    </div>
                    <Actions>
                      <Reject busy={busy} onClick={() => act(() => hideTip(t.id))}>
                        Verbergen
                      </Reject>
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
        <div className="text-[13px] text-muted">
          von {submission.submitter_name} ·{" "}
          {new Date(submission.created_at).toLocaleDateString("de-DE")}
        </div>

        {complete ? (
          <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-band p-2 text-[12px] text-ink-soft">
            {JSON.stringify(submission.payload, null, 2)}
          </pre>
        ) : (
          <div className="mt-3 rounded-xl border border-line bg-band/40 p-3">
            <p className="mb-2 text-[12px] font-medium text-muted">
              Nur als Name eingereicht — zum Anlegen Region und Koordinaten ergänzen.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-[12px] text-muted">Region</span>
                <select
                  value={regionId}
                  onChange={(e) => setRegionId(e.target.value)}
                  className="w-full rounded-lg border border-line bg-white px-2 py-1.5 text-[13px] text-ink"
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
                  <span className="mb-1 block text-[12px] text-muted">Breitengrad</span>
                  <input
                    inputMode="decimal"
                    value={lat}
                    onChange={(e) => setLat(e.target.value)}
                    placeholder="54.41"
                    className={`w-full rounded-lg border bg-white px-2 py-1.5 text-[13px] text-ink ${
                      lat && !latOk ? "border-red-300" : "border-line"
                    }`}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[12px] text-muted">Längengrad</span>
                  <input
                    inputMode="decimal"
                    value={lon}
                    onChange={(e) => setLon(e.target.value)}
                    placeholder="10.22"
                    className={`w-full rounded-lg border bg-white px-2 py-1.5 text-[13px] text-ink ${
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
                  className={`rounded-2xl px-2.5 py-1 text-[12px] font-medium ${
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
    <div className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-line bg-white p-4">
      {children}
    </div>
  );
}
function Actions({ children }: { children: React.ReactNode }) {
  return <div className="flex shrink-0 flex-wrap gap-2">{children}</div>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-2xl border border-line bg-white p-6 text-center text-[14px] text-muted">{children}</div>;
}
function Approve({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" disabled={busy} onClick={onClick} className="rounded-lg bg-green px-3 py-1.5 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50">
      {children}
    </button>
  );
}
function Reject({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" disabled={busy} onClick={onClick} className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-[13px] font-medium text-red-700 hover:bg-red-100 disabled:opacity-50">
      {children}
    </button>
  );
}
function Neutral({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" disabled={busy} onClick={onClick} className="rounded-lg border border-teal/30 px-3 py-1.5 text-[13px] font-medium text-teal hover:bg-teal/5 disabled:opacity-50">
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
  return (
    <div className="flex min-w-0 items-start gap-3">
      <img
        src={resolveMediaUrl(url)}
        alt=""
        className="h-20 w-32 shrink-0 rounded-lg object-cover"
      />
      <div className="min-w-0 text-[13px]">
        {credit && <div className="text-ink">Credit: {credit}</div>}
        {badge && <div className="font-medium text-ink">{badge}</div>}
        <Link to={`/admin/spot/${spotId}/edit`} className="text-muted hover:underline">
          Zum Spot
        </Link>
      </div>
    </div>
  );
}
