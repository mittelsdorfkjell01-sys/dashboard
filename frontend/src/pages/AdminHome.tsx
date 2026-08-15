// Admin overview, activity-oriented (Sprint 10): leads with a prioritized
// "Was ist zu tun?" list that surfaces everything needing an operator's
// attention — moderation, review, ready-to-publish, spots to finish — each with
// a direct link. Raw counters are demoted to a compact strip at the bottom.

import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ApiError,
  getAdminOverview,
  type AdminOverview,
  type Rank,
  type RankedSpot,
} from "../lib/api";
import { gapLabel } from "../lib/labels";
import { RANK_CARD, RANK_DOT } from "../lib/rank";
import BoardPanel from "../components/admin/BoardPanel";
import { Badge, type BadgeTone } from "../components/admin/ui";
import { createAdminReturnState } from "../lib/adminNavigation";

type Tone = "red" | "orange" | "teal";
interface Task {
  key: string;
  tone: Tone;
  label: string;
  count: number;
  to: string;
}

const TONE_BADGE: Record<Tone, BadgeTone> = {
  red: "danger",
  orange: "warning",
  teal: "primary",
};

function buildTasks(data: AdminOverview): Task[] {
  const r = data.review ?? {};
  const n = (k: string) => r[k] ?? 0;
  const reported = n("reported_images") + n("flagged_tips") + n("flagged_ratings");
  const pending =
    n("submissions_pending") + n("hero_candidates_pending") + n("gallery_images_pending");
  const readyToPublish = data.drafts.filter((d) => d.ready).length;

  const tasks: Task[] = [];
  if (reported > 0)
    tasks.push({ key: "reported", tone: "red", label: "Gemeldete Beiträge moderieren", count: reported, to: "/admin/review" });
  if (pending > 0)
    tasks.push({ key: "pending", tone: "orange", label: "Neue Einreichungen prüfen", count: pending, to: "/admin/review" });
  if (readyToPublish > 0)
    tasks.push({ key: "ready", tone: "teal", label: "Bereit zum Veröffentlichen", count: readyToPublish, to: "/admin/spots?status=draft" });
  // Note: "Spots fertigstellen" is intentionally NOT a task here — the same open
  // spots are shown as a working list in the "Fertigstellen" panel below, so
  // listing them twice (once as a count, once as a list) only read as redundant.
  return tasks;
}

export default function AdminHome() {
  const location = useLocation();
  const editorState = createAdminReturnState(location, "Übersicht");
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminOverview()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen."));
  }, []);

  if (error)
    return (
      <div role="alert" className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-4 py-3 text-label text-admin-danger">
        {error}
      </div>
    );
  if (!data)
    return <div role="status" className="text-label text-admin-muted">Lädt…</div>;

  const tasks = buildTasks(data);

  return (
    <div>
      <h1 className="sr-only">Übersicht</h1>
      {/* Region-less spots — most urgent, flagged red at the very top. */}
      {data.no_region.length > 0 && (
        <section className="rounded-2xl border-2 border-red-400 bg-red-50/50 p-4">
          <p className="text-body font-semibold text-red-700">
            {data.no_region.length} Spot(s) ohne Region
          </p>
          <p className="mt-0.5 text-caption text-red-700/80">
            Diesen Spots ist keine Region zugeordnet — bitte eine Region wählen,
            sonst erscheinen sie nicht korrekt auf der Seite.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.no_region.map((s) => (
              <Link
                key={s.id}
                to={`/admin/spot/${s.id}/edit`}
                state={editorState}
                className="rounded-lg bg-white px-3 py-1.5 text-label font-medium text-red-700 ring-1 ring-red-300 hover:bg-admin-danger-bg"
              >
                {s.name} →
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Team board — directly under the region-less (red) block, above the
          "Fertigstellen" working list. Replaces the old Team-Notizen. */}
      <section className={data.no_region.length > 0 ? "mt-6" : ""}>
        <h2 className="text-body font-semibold text-ink">Board</h2>
        <div className="mt-3">
          <BoardPanel />
        </div>
      </section>

      {/* Was ist zu tun? — the prioritized action list (hidden when empty; the
          board already conveys "nothing to do"). */}
      {tasks.length > 0 && (
        <section className="mt-6 overflow-hidden rounded-lg border border-admin-border bg-admin-surface">
          <ul className="divide-y divide-admin-border">
            {tasks.map((t) => (
              <li key={t.key}>
                <Link
                  to={t.to}
                  className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-admin-hover"
                >
                  <span className="flex-1 text-body text-admin-fg">{t.label}</span>
                  <Badge tone={TONE_BADGE[t.tone]}>{t.count}</Badge>
                  <span aria-hidden className="text-admin-faint">›</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(data.climatology_missing > 0 ||
        data.climatology_stale > 0 ||
        data.climatology_failed > 0) && (
        <p className="mt-4 border-y border-line px-3 py-3 text-caption text-muted">
          Klimatologie: {data.climatology_missing} fehlend, {data.climatology_stale}{" "}
          veraltet, {data.climatology_failed} fehlgeschlagen. Veraltete und bei
          Live-Spots fehlende Daten werden automatisch aktualisiert.
        </p>
      )}

      {/* Fertigstellen — spots still being reworked, split into two columns:
          left the red ones (a lot still to do), right the yellow ones (nearly
          done). Green (finished) spots drop out of the list entirely. Each row
          links straight to the editor — go-live/archive live on the Spots page. */}
      <section className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-label font-semibold text-admin-fg">Fertigstellen</h2>
          <span className="text-caption text-admin-muted">
            ({data.finish.filter((f) => f.rank !== "green").length})
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <FinishColumn
            title="Viel zu tun"
            rank="red"
            spots={data.finish.filter((f) => f.rank === "red")}
            editorState={editorState}
          />
          <FinishColumn
            title="Fast fertig"
            rank="yellow"
            spots={data.finish.filter((f) => f.rank === "yellow")}
            editorState={editorState}
          />
        </div>
      </section>

      {/* Secondary: raw counters */}
      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Entwürfe" value={data.spots.draft} to="/admin/spots?status=draft" />
        <Tile label="Veröffentlicht" value={data.spots.published} to="/admin/spots?status=published" accent="green" />
        <Tile label="Archiviert" value={data.spots.archived} to="/admin/spots?status=archived" />
        <Tile label="Regionen" value={data.regions} to="/admin/regions" />
      </div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-2 text-caption text-admin-muted">{children}</p>;
}

// One Fertigstellen column (red = viel zu tun, yellow = fast fertig). Rows link
// straight to the editor; no per-row ops here.
function FinishColumn({
  title,
  rank,
  spots,
  editorState,
}: {
  title: string;
  rank: Rank;
  spots: RankedSpot[];
  editorState: ReturnType<typeof createAdminReturnState>;
}) {
  return (
    <section className="rounded-lg border border-admin-border bg-admin-surface p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${RANK_DOT[rank]}`} />
        <h3 className="text-label font-semibold text-admin-fg">{title}</h3>
        <span className="text-caption text-admin-muted">({spots.length})</span>
      </div>
      <div className="space-y-2">
        {spots.length === 0 ? (
          <Empty>Keine Spots.</Empty>
        ) : (
          spots.map((s) => (
            <Link
              key={s.id}
              to={`/admin/spot/${s.id}/edit`}
              state={editorState}
              className={`flex flex-wrap items-center gap-3 rounded-lg border p-3 transition-colors hover:brightness-105 ${RANK_CARD[rank]}`}
            >
              <span className="min-w-0 flex-1">
                <span className="text-label font-medium text-ink">{s.name}</span>
                <span className="mt-0.5 block text-caption text-muted">
                  {s.gaps.length === 0
                    ? "Fertig — nichts offen"
                    : `Offen: ${s.gaps.map(gapLabel).join(", ")}`}
                </span>
              </span>
            </Link>
          ))
        )}
      </div>
    </section>
  );
}

function Tile({
  label,
  value,
  to,
  accent,
}: {
  label: string;
  value: number;
  to: string;
  accent?: "green";
}) {
  return (
    <Link
      to={to}
      className="rounded-lg border border-admin-border bg-admin-surface p-4 transition-colors hover:border-admin-border-strong hover:bg-admin-hover"
    >
      {/* Counters are secondary: kept deliberately quiet (smaller numerals) so
          the prioritised task list above wins the squint test. */}
      <div
        className={`admin-mono text-[20px] font-semibold leading-none ${
          accent === "green" ? "text-admin-success" : "text-admin-fg2"
        }`}
      >
        {value}
      </div>
      <div className="mt-1.5 text-caption text-admin-muted">{label}</div>
    </Link>
  );
}
