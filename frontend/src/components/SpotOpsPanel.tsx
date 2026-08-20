// Operations panel for a saved spot: status, calibration, save + go-live /
// offline / archive. Embedded in AdminSpotForm in edit mode. Explicit
// calculations run inline; durable refreshes use the maintenance queue.

import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  ApiError,
  archiveSpot,
  getEra5Status,
  getReadiness,
  getAdminSpot,
  goLiveSpot,
  reactivateSpot,
  setFinishRank as saveFinishRank,
  triggerEra5,
  unpublishSpot,
  type Era5Status,
  type Rank,
  type Readiness,
} from "../lib/api";
import { gapLabel } from "../lib/labels";
import { effectiveRank, RANK_DOT, RANK_LABEL } from "../lib/rank";
import RankControl from "./admin/RankControl";
import ConfirmToast from "./admin/ConfirmToast";
import { Button } from "./admin/ui";

const ERA5_LABEL: Record<string, string> = {
  queued: "in Warteschlange",
  processing: "wird berechnet",
  extracting: "wird verarbeitet",
  derived: "aktuell",
  current: "aktuell",
  stale: "veraltet",
  missing: "nicht berechnet",
  failed: "fehlgeschlagen",
  none: "nicht berechnet",
};

export default function SpotOpsPanel({
  spotId,
  spotName,
  regionName,
  onGapClick,
  submitting,
  saveLabel = "Änderungen speichern",
  cancelSlot,
  previewHref,
  secondarySaveAction,
}: {
  spotId: string;
  /** Spot name — rendered as the panel's identity header. */
  spotName?: string;
  /** Region name — the muted subtitle under the spot name. */
  regionName?: string;
  /** Click a readiness gap to jump to its field in the form. */
  onGapClick?: (gap: string) => void;
  /** Wired to the outer form's submit state — the button lives here now. */
  submitting?: boolean;
  saveLabel?: string;
  /** The form's cancel control (AdminBackButton); rendered inline as a link. */
  cancelSlot?: ReactNode;
  /** When present, shows the "Öffentliche Vorschau" link. */
  previewHref?: string;
  secondarySaveAction?: ReactNode;
}) {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [overrides, setOverrides] = useState<Record<string, unknown> | null>(null);
  const [rankOverride, setRankOverride] = useState<Rank | null>(null);
  const [era5, setEra5] = useState<Era5Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingArchive, setPendingArchive] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [r, spot, e] = await Promise.all([
      getReadiness(spotId).catch(() => null),
      getAdminSpot(spotId).catch(() => null),
      getEra5Status(spotId).catch(() => null),
    ]);
    setReadiness(r);
    setOverrides(spot?.overrides ?? null);
    setRankOverride(spot?.finish_rank ?? null);
    setEra5(e);
  }, [spotId]);

  const onRankChange = async (rank: Rank | null) => {
    const prev = rankOverride;
    setRankOverride(rank); // optimistic
    try {
      await saveFinishRank(spotId, rank);
    } catch (e) {
      setRankOverride(prev); // rollback
      setError(e instanceof ApiError ? e.message : "Rang konnte nicht gesetzt werden.");
    }
  };

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3000);
  };

  const onGoLive = async () => {
    setBusy(true);
    setError(null);
    try {
      // Publishing enforces editorial completeness: the API blocks an
      // incomplete spot with 409 + the blocking gaps (handled below).
      const res = (await goLiveSpot(spotId)) as { ready?: boolean; gaps?: string[] };
      const gaps = res.gaps ?? [];
      const climate = (res as {
        climatology_job?: { status?: string; detail?: string };
      }).climatology_job;
      if (climate?.status === "fail") {
        setError(
          `Spot ist live, aber die Klimatologie konnte nicht berechnet werden: ${
            climate.detail ?? "Unbekannter Fehler"
          }`
        );
      }
      flash(
        res.ready === false && gaps.length > 0
          ? `Live gesetzt — es fehlen noch: ${gaps.map(gapLabel).join(", ")}`
          : "Spot ist jetzt live."
      );
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = e.detail as { message?: string; gaps?: string[] } | undefined;
        const gaps = detail?.gaps ?? [];
        setError(
          gaps.length > 0
            ? `Nicht veröffentlicht — es fehlen: ${gaps.map(gapLabel).join(", ")}`
            : detail?.message ?? e.message
        );
      } else {
        setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const runStatus = async (fn: () => Promise<unknown>, msg: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      flash(msg);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const onTriggerEra5 = () =>
    runStatus(() => triggerEra5(spotId), "Klimatologie wurde berechnet.");

  const overrideKeys = overrides ? Object.keys(overrides) : [];
  const era5Status = era5?.status ?? "none";
  const generatedAt = era5?.generated_at
    ? new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(
        new Date(era5.generated_at)
      )
    : null;
  const rank = effectiveRank(readiness?.gaps ?? [], rankOverride);

  const status = readiness?.status ?? "draft";
  const statusInfo: Record<string, { label: string; dot: string; pill: string }> = {
    draft: {
      label: "Entwurf",
      dot: "bg-admin-muted",
      pill: "border border-admin-border bg-admin-bg text-admin-fg2",
    },
    published: {
      label: "Veröffentlicht",
      dot: "bg-admin-success",
      pill: "bg-admin-success-bg text-admin-success",
    },
    archived: {
      label: "Archiviert",
      dot: "bg-admin-faint",
      pill: "border border-admin-border bg-admin-bg text-admin-muted",
    },
  };
  const s = statusInfo[status] ?? statusInfo.draft;

  return (
    <div className="rounded-lg border border-admin-border bg-admin-surface">
      {/* Identität — Spotname + Region tragen die Kachel; der Status sitzt als
          Pille rechts oben. Ersetzt die frühere „Betrieb & Veröffentlichung"-
          Überschrift, deren Sinn sich aus den Steuerungen darunter ergibt. */}
      <div className="flex items-start justify-between gap-3 border-b border-admin-border px-5 py-4">
        <div className="min-w-0">
          <p className="truncate text-body font-semibold text-admin-fg">
            {spotName?.trim() || "Unbenannter Spot"}
          </p>
          <p className="mt-0.5 truncate text-label text-admin-muted">
            {regionName || "Ohne Region"}
          </p>
        </div>
        <span
          className={`mt-0.5 inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-caption font-medium ${s.pill}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
          {s.label}
        </span>
      </div>

      <ConfirmToast
        open={pendingArchive}
        message="Spot archivieren?"
        busy={busy}
        onConfirm={() => {
          setPendingArchive(false);
          void runStatus(() => archiveSpot(spotId), "Spot archiviert.");
        }}
        onCancel={() => setPendingArchive(false)}
      />

      <div className="p-5">
        {/* 1) Readiness — was für die Veröffentlichung noch fehlt. Direkt unter
               dem Status, als eigener gerahmter Block statt loser Zeile. */}
        {readiness && !readiness.ready && readiness.gaps.length > 0 && (
          <div className="mb-5 rounded-md border border-admin-border bg-admin-bg px-3 py-2.5">
            <p className="text-caption font-medium uppercase tracking-wide text-admin-muted">
              Für die Veröffentlichung fehlt
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {readiness.gaps.map((g) =>
                onGapClick ? (
                  <button
                    key={g}
                    type="button"
                    onClick={() => onGapClick(g)}
                    className="rounded-md bg-admin-warning-bg px-2 py-0.5 text-caption font-medium text-admin-warning transition-colors hover:brightness-110"
                  >
                    {gapLabel(g)}
                  </button>
                ) : (
                  <span
                    key={g}
                    className="rounded-md bg-admin-warning-bg px-2 py-0.5 text-caption font-medium text-admin-warning"
                  >
                    {gapLabel(g)}
                  </span>
                )
              )}
            </div>
          </div>
        )}

        {/* 2) Primäraktion — Speichern. Steht oben, weil es die tägliche
               Redigier-Aktion ist. */}
        <Button type="submit" variant="primary" block disabled={submitting} className="min-h-11">
          {submitting ? "Speichern …" : saveLabel}
        </Button>
        {secondarySaveAction && <div className="mt-2 hidden xl:block">{secondarySaveAction}</div>}
        {(cancelSlot || previewHref) && (
          <div className="mt-3 flex items-center justify-between text-label">
            {cancelSlot ?? <span />}
            {previewHref && (
              <a
                href={previewHref}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-admin-primary hover:underline"
                title="Öffnet die öffentliche Spot-Seite — funktioniert auch für Entwürfe."
              >
                Öffentliche Vorschau ↗
              </a>
            )}
          </div>
        )}

        {notice && (
          <p className="mt-3 text-label font-medium text-admin-success">{notice}</p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-label font-medium text-admin-danger">
            {error}
          </p>
        )}

        {/* 3) Einstellungen — Klimatologie + Fertigstellen-Rang. */}
        <div className="mt-5 space-y-4 border-t border-admin-border pt-5">
          <div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-label font-medium text-admin-fg">Klimatologie</span>
              <span className="text-label text-admin-fg2">
                {ERA5_LABEL[era5Status] ?? era5Status}
              </span>
            </div>
            {(era5?.window || generatedAt) && (
              <p className="mt-1 text-caption text-admin-faint">
                {[era5?.window ? `Zeitraum ${era5.window}` : null,
                  generatedAt ? `berechnet am ${generatedAt}` : null]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
            {era5?.freshness_status === "stale" &&
              ["queued", "processing", "extracting"].includes(era5Status) && (
                <p className="mt-1 text-caption text-admin-muted">
                  Die bisherigen Werte bleiben bis zur erfolgreichen Aktualisierung aktiv.
                </p>
              )}
            {era5?.error && (
              <p className="mt-1 break-words text-caption text-admin-danger">{era5.error}</p>
            )}
            <Button variant="secondary" disabled={busy} onClick={onTriggerEra5} className="mt-2.5">
              Neu berechnen
            </Button>
          </div>

          <div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-label font-medium text-admin-fg">Fertigstellen-Rang</span>
              <span className="inline-flex items-center gap-1.5 text-label text-admin-fg2">
                <span className={`h-2 w-2 rounded-full ${RANK_DOT[rank]}`} />
                {RANK_LABEL[rank]}
                <span
                  className={`text-caption text-admin-faint ${
                    rankOverride === null ? "" : "invisible"
                  }`}
                >
                  auto
                </span>
              </span>
            </div>
            <div className="mt-2.5">
              <RankControl value={rankOverride} effective={rank} onChange={onRankChange} busy={busy} />
            </div>
          </div>
        </div>

        {/* 4) Lebenszyklus — situative Aktionen, keine Tagesarbeit. Reaktivieren
               im Archiv, sonst Go-Live/Offline + Archivieren. */}
        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-admin-border pt-5">
          {status === "archived" ? (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                runStatus(() => reactivateSpot(spotId), "Spot ist wieder ein Entwurf.")
              }
            >
              Reaktivieren
            </Button>
          ) : (
            <>
              {status !== "published" && (
                <Button variant="secondary" disabled={busy} onClick={onGoLive}>
                  Go-Live
                </Button>
              )}
              {status === "published" && (
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => runStatus(() => unpublishSpot(spotId), "Spot ist offline.")}
                >
                  Offline nehmen
                </Button>
              )}
              <Button
                variant="ghost"
                disabled={busy || pendingArchive}
                onClick={() => setPendingArchive(true)}
              >
                Archivieren
              </Button>
            </>
          )}
        </div>

        {overrideKeys.length > 0 && (
          <div className="mt-5 border-t border-admin-border pt-5">
            <p className="text-label font-semibold text-admin-fg">Überschriebene Felder</p>
            <ul className="mt-2 space-y-1.5">
              {overrideKeys.map((k) => (
                <li key={k} className="flex items-center gap-2 text-label text-admin-fg2">
                  <span className="admin-mono font-medium">{k}</span>
                  <span className="admin-mono text-admin-muted">= {JSON.stringify(overrides?.[k])}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
