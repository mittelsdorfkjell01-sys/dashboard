// Admin overview, activity-oriented (Sprint 10): leads with a prioritized
// "Was ist zu tun?" list that surfaces everything needing an operator's
// attention — moderation, review, ready-to-publish, spots to finish — each with
// a direct link. Raw counters are demoted to a compact strip at the bottom.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getAdminOverview, type AdminOverview } from "../lib/api";
import { gapLabel } from "../lib/labels";
import TeamBoard from "../components/admin/TeamBoard";

type Tone = "red" | "orange" | "teal";
interface Task {
  key: string;
  tone: Tone;
  label: string;
  count: number;
  to: string;
}

const TONE_DOT: Record<Tone, string> = {
  red: "bg-red-500",
  orange: "bg-orange",
  teal: "bg-teal",
};
const TONE_BADGE: Record<Tone, string> = {
  red: "bg-red-50 text-red-700",
  orange: "bg-orange/15 text-ink",
  teal: "bg-teal/10 text-teal",
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
      <div role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-label text-red-700">
        {error}
      </div>
    );
  if (!data)
    return <div role="status" className="text-label text-muted">Lädt…</div>;

  const tasks = buildTasks(data);

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-ui font-semibold text-ink sm:text-editorial-4">Übersicht</h1>
          <p className="mt-1 text-label text-muted">Was ist zu tun? Alles Offene auf einen Blick.</p>
        </div>
        <Link
          to="/admin/spot/new"
          className="shrink-0 rounded-lg bg-teal px-4 py-2 text-label font-medium text-white hover:bg-teal-hover"
        >
          + Neuer Spot
        </Link>
      </div>

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

      {/* Was ist zu tun? — the prioritized action list */}
      <section className="mt-6 overflow-hidden rounded-2xl border border-line bg-white">
        {tasks.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-ui font-semibold text-ink">Alles erledigt 🎉</p>
            <p className="mt-1 text-label text-muted">Keine offenen Aufgaben.</p>
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {tasks.map((t) => (
              <li key={t.key}>
                <Link
                  to={t.to}
                  className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-band/60"
                >
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${TONE_DOT[t.tone]}`} />
                  <span className="flex-1 text-body text-ink">{t.label}</span>
                  <span className={`min-w-[26px] rounded-full px-2 py-0.5 text-center text-caption font-semibold ${TONE_BADGE[t.tone]}`}>
                    {t.count}
                  </span>
                  <span aria-hidden className="text-muted">›</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.era5_queued > 0 && (
        <div className="mt-4 rounded-2xl border border-line bg-teal/5 p-3 text-caption text-muted">
          {data.era5_queued} Spot(s): Klimatologie wird im Hintergrund berechnet — Windmonate
          erscheinen automatisch, sobald sie fertig ist.
        </div>
      )}

      {/* Kanban board — team tasks, kept above the fold (above "Fertigstellen"). */}
      <TeamBoard />

      {/* Unfinished spots — one place. The count is the true open total; the list
          shows the first ones with a link to the rest. */}
      <section className="mt-6">
        <Panel title="Fertigstellen" count={data.readiness_open}>
          {data.not_live.length === 0 ? (
            <Empty>Keine unfertigen Spots. 🎉</Empty>
          ) : (
            <>
              {data.not_live.map((s) => (
                <Link
                  key={s.id}
                  to={`/admin/spot/${s.id}/edit`}
                  className="block rounded-lg bg-orange/5 p-3 transition-colors hover:bg-orange/10"
                >
                  <p className="text-label font-medium text-ink">{s.name}</p>
                  <p className="mt-0.5 text-caption text-muted">
                    Fehlt: {s.gaps.map(gapLabel).join(", ")}
                  </p>
                </Link>
              ))}
              {data.readiness_open > data.not_live.length && (
                <Link
                  to="/admin/spots?status=draft"
                  className="block rounded-lg p-2 text-center text-caption font-medium text-teal hover:bg-teal/5"
                >
                  +{data.readiness_open - data.not_live.length} weitere anzeigen →
                </Link>
              )}
            </>
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
    <section className="rounded-2xl border border-line bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-label font-semibold text-ink">{title}</h2>
        <span className="text-caption text-muted">({count})</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-2 text-caption text-muted">{children}</p>;
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
    <Link to={to} className="rounded-2xl border border-line bg-white p-4 transition-colors hover:border-teal/40">
      <div className={`text-3xl font-semibold leading-none ${accent === "green" ? "text-green" : "text-ink"}`}>
        {value}
      </div>
      <div className="mt-1 text-caption text-muted">{label}</div>
    </Link>
  );
}
