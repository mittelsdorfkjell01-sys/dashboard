// Admin overview, activity-oriented (Sprint 10): leads with a prioritized
// "Was ist zu tun?" list that surfaces everything needing an operator's
// attention — moderation, review, ready-to-publish, spots to finish — each with
// a direct link. Raw counters are demoted to a compact strip at the bottom.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  getAdminOverview,
  type AdminOverview,
} from "../lib/api";
import { gapLabel } from "../lib/labels";
import { RANK_CARD, RANK_DOT } from "../lib/rank";
import BoardPanel from "../components/admin/BoardPanel";
import { Badge, type BadgeTone } from "../components/admin/ui";

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
      {/* Region-less spots — most urgent, flagged red at the very top. */}
      {data.no_region.length > 0 && (
        <section className="mt-6 rounded-2xl border-2 border-red-400 bg-red-50/50 p-4">
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
                className="rounded-lg bg-white px-3 py-1.5 text-label font-medium text-red-700 ring-1 ring-red-300 hover:bg-red-100"
              >
                {s.name} →
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Team board — directly under the region-less (red) block, above the
          "Fertigstellen" working list. Replaces the old Team-Notizen. */}
      <section className="mt-6">
        <h2 className="text-body font-semibold text-ink">Board</h2>
        <p className="mt-1 text-label text-muted">Aufgaben fürs Team.</p>
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

      {data.era5_queued > 0 && (
        <div className="mt-4 rounded-2xl border border-line bg-teal/5 p-3 text-caption text-muted">
          {data.era5_queued} Spot(s): Klimatologie wird im Hintergrund berechnet — Windmonate
          erscheinen automatisch, sobald sie fertig ist.
        </div>
      )}

      {/* Fertigstellen — the whole catalogue is being reworked, so every spot is
          listed here with its traffic-light rank (worst first). The count is how
          many still need work (not green). Rank can be set per row (Auto = derived
          from the open points; a colour pins it manually). */}
      <section className="mt-6">
        <Panel
          title="Fertigstellen"
          count={data.finish.filter((f) => f.rank !== "green").length}
        >
          {data.finish.length === 0 ? (
            <Empty>Keine Spots.</Empty>
          ) : (
            data.finish.map((s) => (
              <div
                key={s.id}
                className={`flex flex-wrap items-center gap-3 rounded-lg border p-3 ${RANK_CARD[s.rank]}`}
              >
                <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${RANK_DOT[s.rank]}`} />
                <Link
                  to={`/admin/spot/${s.id}/edit`}
                  className="min-w-0 flex-1 hover:underline"
                >
                  <span className="text-label font-medium text-ink">{s.name}</span>
                  <span className="mt-0.5 block text-caption text-muted">
                    {s.gaps.length === 0
                      ? "Fertig — nichts offen"
                      : `Offen: ${s.gaps.map(gapLabel).join(", ")}`}
                  </span>
                </Link>
              </div>
            ))
          )}
        </Panel>
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

function Panel({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-admin-border bg-admin-surface p-4">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-label font-semibold text-admin-fg">{title}</h2>
        <span className="text-caption text-admin-muted">({count})</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-2 text-caption text-admin-muted">{children}</p>;
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
      <div
        className={`admin-mono text-[28px] font-semibold leading-none ${
          accent === "green" ? "text-admin-success" : "text-admin-fg"
        }`}
      >
        {value}
      </div>
      <div className="mt-1.5 text-caption text-admin-muted">{label}</div>
    </Link>
  );
}
