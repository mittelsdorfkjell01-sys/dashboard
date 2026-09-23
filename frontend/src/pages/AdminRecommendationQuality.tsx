import { useCallback, useEffect, useState } from "react";
import { Badge, Button, PageHeader, type BadgeTone } from "../components/admin/ui";
import { useAuth } from "../lib/auth";
import {
  ApiError,
  createAdminCalibrationProposal,
  decideAdminCalibrationProposal,
  getAdminRecommendationQuality,
  getAdminScoringCalibration,
  type CalibrationPreview,
  type CalibrationProposal,
  type RecommendationQuality,
  type ScoringCalibration,
} from "../lib/api";

const AUDIENCE: Record<string, string> = {
  logged_profile: "Eingeloggt mit Profil",
  logged_without_profile: "Eingeloggt ohne Profil",
  anonymous: "Anonym",
};

const KIND: Record<CalibrationProposal["kind"], string> = {
  default_rider: "Durchschnitts-Rider",
  personal_band: "Personal Band",
  social_weight: "Sozialsignal",
};

function percent(value: number | null): string {
  return value == null
    ? "—"
    : new Intl.NumberFormat("de-DE", { style: "percent", maximumFractionDigits: 1 }).format(value);
}

function dateTime(value: string | null): string {
  return value ? new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
}

function PreviewCard({
  title,
  preview,
  onCreate,
  busy,
}: {
  title: string;
  preview: CalibrationPreview;
  onCreate: () => void;
  busy: boolean;
}) {
  const minimum = preview.minimum_profiles ?? preview.minimum_checkins ?? 0;
  return (
    <section className="rounded-lg border border-admin-border bg-admin-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-label font-semibold text-admin-fg">{title}</h3>
          <p className="mt-1 text-caption text-admin-muted">
            {preview.sample_count} von mindestens {minimum} auswertbaren Datensätzen
          </p>
        </div>
        <Badge tone={preview.eligible ? "success" : "warning"}>
          {preview.eligible ? "Bereit" : "Wartet auf Daten"}
        </Badge>
      </div>
      <Button
        className="mt-4"
        variant="primary"
        disabled={!preview.eligible || busy}
        onClick={onCreate}
      >
        {busy ? "Wird erstellt …" : "Vorschlag erstellen"}
      </Button>
      {preview.observations && preview.observations.length > 0 && (
        <div className="mt-4 overflow-x-auto border-t border-admin-border pt-3">
          <p className="mb-2 text-caption font-medium text-admin-fg2">Lohnende Check-ins nach Schirm</p>
          <table className="w-full min-w-[360px] text-left text-caption">
            <thead className="text-admin-muted"><tr><th className="pb-1 font-medium">Kite</th><th className="pb-1 font-medium">Board</th><th className="pb-1 font-medium">Wind p10–p90</th><th className="pb-1 text-right font-medium">n</th></tr></thead>
            <tbody className="divide-y divide-admin-border-subtle">
              {preview.observations.map((row) => (
                <tr key={`${row.kite_size}-${row.board_type}`}>
                  <td className="py-1.5 text-admin-fg">{row.kite_size} m²</td>
                  <td className="py-1.5">{row.board_type}</td>
                  <td className="admin-mono py-1.5">{row.p10_wind_kt}–{row.p90_wind_kt} kn</td>
                  <td className="admin-mono py-1.5 text-right">{row.sample_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function proposalTone(status: CalibrationProposal["status"]): BadgeTone {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  return "warning";
}

export default function AdminRecommendationQuality() {
  const { user } = useAuth();
  const [days, setDays] = useState(30);
  const [quality, setQuality] = useState<RecommendationQuality | null>(null);
  const [calibration, setCalibration] = useState<ScoringCalibration | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextQuality, nextCalibration] = await Promise.all([
        getAdminRecommendationQuality(days),
        getAdminScoringCalibration(),
      ]);
      setQuality(nextQuality);
      setCalibration(nextCalibration);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Empfehlungsqualität konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { void load(); }, [load]);

  const createProposal = async (kind: "default_rider" | "personal_band") => {
    setBusy(kind); setError(null); setMessage(null);
    try {
      await createAdminCalibrationProposal(kind);
      setMessage("Der Vorschlag wurde angelegt und wartet auf eine Admin-Entscheidung.");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Vorschlag konnte nicht erstellt werden.");
    } finally { setBusy(null); }
  };

  const decide = async (proposal: CalibrationProposal, decision: "approve" | "reject") => {
    setBusy(proposal.id); setError(null); setMessage(null);
    try {
      const result = await decideAdminCalibrationProposal(proposal.id, decision);
      setMessage(decision === "approve"
        ? `Version ${result.activated_params_version} wurde aktiviert.`
        : "Der Vorschlag wurde abgelehnt.");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Entscheidung konnte nicht gespeichert werden.");
    } finally { setBusy(null); }
  };

  return (
    <div>
      <PageHeader title="Empfehlungsqualität" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-admin-fg">Empfehlungsqualität</h2>
          <p className="mt-1 max-w-2xl text-caption text-admin-muted">
            Nutzungssignale, Check-ins und freigabepflichtige Kalibrierung nach Parametersatz.
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-admin-border bg-admin-surface p-1" aria-label="Auswertungszeitraum">
          {[30, 90, 180].map((value) => (
            <Button key={value} variant={days === value ? "primary" : "ghost"} onClick={() => setDays(value)}>
              {value} Tage
            </Button>
          ))}
        </div>
      </div>

      {error && <div role="alert" className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label text-admin-danger">{error}</div>}
      {message && <div role="status" className="mt-4 rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label text-admin-success">{message}</div>}
      {loading && !quality && <p role="status" className="mt-6 text-admin-muted">Kennzahlen werden geladen …</p>}

      {quality && (
        <>
          <div className="mt-6 flex flex-wrap gap-x-8 gap-y-2 rounded-lg border border-admin-border bg-admin-surface px-4 py-3 text-caption text-admin-muted">
            <span>Berechnungen <strong className="admin-mono ml-1 text-admin-fg">{quality.totals.recommendation_calculations}</strong></span>
            <span>Ausgewertete Events <strong className="admin-mono ml-1 text-admin-fg">{quality.totals.events}</strong></span>
          </div>

          <div tabIndex={0} aria-label="Qualitätskennzahlen horizontal scrollen" className="mt-4 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-admin-primary">
            <table className="w-full min-w-[880px] text-left text-ui">
              <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase text-admin-muted">
                <tr>
                  {["Surface", "Zielgruppe", "Params", "Impressions", "CTR", "Favorisierung", "Check-in", "Lohnend"].map((label) => <th key={label} className="px-3 py-2.5 font-semibold">{label}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-admin-border-subtle">
                {quality.rows.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-admin-muted">Für diesen Zeitraum liegen noch keine zuordenbaren Events vor.</td></tr>
                ) : quality.rows.map((row) => (
                  <tr key={`${row.surface}-${row.audience}-${row.params_version}`}>
                    <td className="px-3 py-3 font-medium text-admin-fg">{row.surface}</td>
                    <td className="px-3 py-3">{AUDIENCE[row.audience] ?? row.audience}</td>
                    <td className="admin-mono px-3 py-3">v{row.params_version}</td>
                    <td className="admin-mono px-3 py-3">{row.impressions}</td>
                    <td className="admin-mono px-3 py-3">{percent(row.ctr)}</td>
                    <td className="admin-mono px-3 py-3">{percent(row.favorite_rate)}</td>
                    <td className="admin-mono px-3 py-3">{percent(row.checkin_rate)}</td>
                    <td className="admin-mono px-3 py-3">{percent(row.worthwhile_share)} <span className="text-admin-muted">({row.checkins_with_outcome})</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {calibration && (
        <>
          <div className="mt-10 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-admin-fg">Kalibrierung</h2>
              <p className="mt-1 text-caption text-admin-muted">Aktiver Parametersatz: v{calibration.active_params_version}</p>
            </div>
            <Badge tone={calibration.social.validated ? "success" : "neutral"}>
              Sozialsignal {calibration.social.validated ? "aktiv" : "wartet auf Verbesserungsevidenz"}
            </Badge>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <PreviewCard title="Durchschnitts-Rider" preview={calibration.default_rider} busy={busy === "default_rider"} onCreate={() => void createProposal("default_rider")} />
            <PreviewCard title="Personal Band" preview={calibration.personal_band} busy={busy === "personal_band"} onCreate={() => void createProposal("personal_band")} />
            <section className="rounded-lg border border-admin-border bg-admin-surface p-4">
              <h3 className="text-label font-semibold text-admin-fg">Sozialsignal</h3>
              <p className="mt-1 text-caption text-admin-muted">Startgewicht {percent(calibration.social.weight ?? 0)} · Mindestgruppe {calibration.social.min_group_size ?? "—"}</p>
              <p className="mt-4 text-caption text-admin-muted">Eine Aktivierung wird nur aus einem dokumentierten Backtest- oder Online-Vergleich angelegt.</p>
            </section>
          </div>

          <h2 className="mt-10 text-label font-semibold text-admin-fg">Änderungsvorschläge</h2>
          <div className="mt-3 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface">
            <table className="w-full min-w-[820px] text-left text-ui">
              <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase text-admin-muted">
                <tr>{["Art", "Basis", "Status", "Erstellt", "Prüfung", "Entscheidung"].map((label) => <th key={label} className="px-3 py-2.5 font-semibold">{label}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-admin-border-subtle">
                {calibration.proposals.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-10 text-center text-admin-muted">Noch keine Vorschläge.</td></tr>
                ) : calibration.proposals.map((proposal) => (
                  <tr key={proposal.id}>
                    <td className="px-3 py-3 font-medium text-admin-fg">{KIND[proposal.kind]}</td>
                    <td className="admin-mono px-3 py-3">v{proposal.base_params_version}</td>
                    <td className="px-3 py-3"><Badge tone={proposalTone(proposal.status)}>{proposal.status}</Badge></td>
                    <td className="px-3 py-3 text-caption">{dateTime(proposal.created_at)}</td>
                    <td className="px-3 py-3">
                      <details className="max-w-sm">
                        <summary className="cursor-pointer text-label font-medium text-admin-fg hover:text-admin-primary">Werte ansehen</summary>
                        <p className="mt-2 text-caption font-medium text-admin-fg2">Vorschlag</p>
                        <pre className="admin-mono mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-admin-hover p-2 text-caption text-admin-fg">{JSON.stringify(proposal.proposed_params, null, 2)}</pre>
                        <p className="mt-2 text-caption font-medium text-admin-fg2">Evidenz</p>
                        <pre className="admin-mono mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-admin-hover p-2 text-caption text-admin-fg">{JSON.stringify(proposal.evidence, null, 2)}</pre>
                      </details>
                    </td>
                    <td className="px-3 py-3">
                      {proposal.status === "pending" && user?.role === "admin" ? (
                        <div className="flex gap-2">
                          <Button variant="primary" disabled={busy === proposal.id} onClick={() => void decide(proposal, "approve")}>Freigeben</Button>
                          <Button disabled={busy === proposal.id} onClick={() => void decide(proposal, "reject")}>Ablehnen</Button>
                        </div>
                      ) : proposal.activated_params_version ? `Aktiv als v${proposal.activated_params_version}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
