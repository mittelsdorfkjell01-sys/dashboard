// Admin overview as three columns:
//   • Offene Punkte     — spots with missing parts (incomplete uploads), per-gap
//   • Entwürfe          — the draft pipeline (each with its open-point count)
//   • Gemeldete Beiträge — reported/flagged community contributions to moderate
// Incomplete spots are saved as drafts (the create path never blocks on missing
// fields), so they flow into "Offene Punkte" / "Entwürfe" to be completed later.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  getAdminOverview,
  type AdminOverview,
} from "../lib/api";
import { gapLabel } from "../lib/labels";

// review-queue keys → German labels. Split into "reported" (user-flagged) and
// "pending" (awaiting a first review).
const REPORTED: { key: string; label: string }[] = [
  { key: "reported_images", label: "Gemeldete Bilder" },
  { key: "flagged_tips", label: "Gemeldete Tipps" },
  { key: "flagged_ratings", label: "Gemeldete Bewertungen" },
];
const PENDING: { key: string; label: string }[] = [
  { key: "submissions_pending", label: "Neue Spot-Vorschläge" },
  { key: "hero_candidates_pending", label: "Neue Bild-Vorschläge" },
  { key: "gallery_images_pending", label: "Neue Galeriebilder" },
];

export default function AdminHome() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminOverview()
      .then(setData)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.")
      );
  }, []);

  if (error) {
    return (
      <div role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-[14px] text-red-700">
        {error}
      </div>
    );
  }
  if (!data)
    return (
      <div role="status" className="text-[14px] text-muted">
        Lädt…
      </div>
    );

  const review = data.review ?? {};
  const reportedTotal = REPORTED.reduce((n, r) => n + (review[r.key] ?? 0), 0);

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-ink">Übersicht</h1>
          <p className="mt-1 text-[14px] text-muted">
            Offene Punkte, Entwürfe und gemeldete Beiträge auf einen Blick.
            Unvollständige Spots werden als Entwurf gespeichert und hier gelistet.
          </p>
        </div>
        <Link
          to="/admin/spot/new"
          className="shrink-0 rounded-xl bg-teal px-4 py-2 text-[14px] font-medium text-white hover:bg-teal-hover"
        >
          + Neuer Spot
        </Link>
      </div>

      {data.era5_queued > 0 && (
        <div className="mt-4 rounded-2xl border border-line bg-orange/5 p-3 text-[13px] text-muted">
          {data.era5_queued} Spot(s): Klimatologie wird im Hintergrund berechnet —
          Windmonate erscheinen automatisch, sobald sie fertig ist.
        </div>
      )}

      {data.team_notes.length > 0 && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.team_notes.map((n) => (
            <div key={n.id} className="rounded-2xl border border-line bg-teal/5 p-4">
              <p className="whitespace-pre-wrap text-[14px] text-ink">{n.body}</p>
              <p className="mt-2 text-[12px] text-muted">
                {n.author ?? "—"} · {new Date(n.created_at).toLocaleDateString("de-DE")}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Status tiles */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Entwürfe" value={data.spots.draft} to="/admin/spots?status=draft" />
        <Tile label="Veröffentlicht" value={data.spots.published} to="/admin/spots?status=published" accent="green" />
        <Tile label="Archiviert" value={data.spots.archived} to="/admin/spots?status=archived" />
        <Tile label="Regionen" value={data.regions} to="/admin/regions" />
      </div>

      {/* Three columns */}
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {/* 1 — Offene Punkte */}
        <Column title="Offene Punkte" count={data.not_live.length} accent="orange">
          {data.not_live.length === 0 ? (
            <Empty>Keine offenen Punkte. 🎉</Empty>
          ) : (
            data.not_live.map((s) => (
              <Link
                key={s.id}
                to={`/admin/spot/${s.id}/edit`}
                className="block rounded-xl bg-orange/5 p-3 transition-colors hover:bg-orange/10"
              >
                <p className="text-[14px] font-medium text-ink">{s.name}</p>
                <p className="mt-0.5 text-[12px] text-muted">
                  Fehlt: {s.gaps.map(gapLabel).join(", ")}
                </p>
              </Link>
            ))
          )}
        </Column>

        {/* 2 — Entwürfe */}
        <Column title="Entwürfe" count={data.drafts.length} accent="ink">
          {data.drafts.length === 0 ? (
            <Empty>Keine Entwürfe.</Empty>
          ) : (
            data.drafts.map((s) => (
              <Link
                key={s.id}
                to={`/admin/spot/${s.id}/edit`}
                className="flex items-center justify-between gap-2 rounded-xl border border-line bg-white p-3 transition-colors hover:bg-teal/5"
              >
                <span className="min-w-0 truncate text-[14px] font-medium text-ink">
                  {s.name}
                </span>
                {s.ready ? (
                  <span className="shrink-0 rounded-full bg-green/10 px-2 py-0.5 text-[11px] font-medium text-green">
                    bereit
                  </span>
                ) : (
                  <span className="shrink-0 rounded-full bg-orange/10 px-2 py-0.5 text-[11px] font-medium text-ink">
                    {s.gaps.length} offen
                  </span>
                )}
              </Link>
            ))
          )}
        </Column>

        {/* 3 — Gemeldete Beiträge */}
        <Column title="Gemeldete Beiträge" count={reportedTotal} accent="red">
          {REPORTED.map((r) => (
            <ReviewRow key={r.key} label={r.label} value={review[r.key] ?? 0} />
          ))}

          <div className="mt-3 border-t border-line pt-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
              Weitere Prüfung
            </p>
            {PENDING.map((r) => (
              <ReviewRow key={r.key} label={r.label} value={review[r.key] ?? 0} />
            ))}
          </div>

          <Link
            to="/admin/review"
            className="mt-3 block rounded-xl bg-teal px-3 py-2 text-center text-[13px] font-medium text-white hover:bg-teal-hover"
          >
            Zur Moderation
          </Link>
        </Column>
      </div>
    </div>
  );
}

function Column({
  title,
  count,
  accent,
  children,
}: {
  title: string;
  count: number;
  accent: "orange" | "ink" | "red";
  children: React.ReactNode;
}) {
  const dot =
    accent === "orange" ? "bg-orange" : accent === "red" ? "bg-red-500" : "bg-ink";
  return (
    <section className="rounded-2xl border border-line bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        <span className="text-[13px] font-normal text-muted">({count})</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function ReviewRow({ label, value }: { label: string; value: number }) {
  return (
    <Link
      to="/admin/review"
      className="flex items-center justify-between rounded-xl px-3 py-2 transition-colors hover:bg-teal/5"
    >
      <span className="text-[14px] text-ink">{label}</span>
      <span
        className={`min-w-[24px] rounded-full px-2 py-0.5 text-center text-[12px] font-semibold ${
          value > 0 ? "bg-red-50 text-red-700" : "bg-line/60 text-muted"
        }`}
      >
        {value}
      </span>
    </Link>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-2 text-[13px] text-muted">{children}</p>;
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
      <div className={`text-[28px] font-semibold ${accent === "green" ? "text-green" : "text-ink"}`}>
        {value}
      </div>
      <div className="mt-0.5 text-[13px] text-muted">{label}</div>
    </Link>
  );
}
