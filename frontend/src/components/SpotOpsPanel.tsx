// Operations panel for a saved spot: readiness + go-live / offline / archive, and
// a read-only view of active overrides. Embedded in AdminSpotForm in edit mode.
// ERA5/climatology runs fully in the background (no manual control here).

import { useCallback, useEffect, useState } from "react";
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
import { gapLabel, statusLabel } from "../lib/labels";
import { effectiveRank, RANK_DOT, RANK_LABEL } from "../lib/rank";
import RankControl from "./admin/RankControl";
import ConfirmToast from "./admin/ConfirmToast";
import { Badge } from "./admin/ui";

const ERA5_LABEL: Record<string, string> = {
  queued: "in Warteschlange",
  processing: "wird berechnet",
  done: "fertig",
  ready: "fertig",
  error: "Fehler",
  none: "nicht berechnet",
};

export default function SpotOpsPanel({
  spotId,
  onGapClick,
}: {
  spotId: string;
  /** Click a readiness gap to jump to its field in the form. */
  onGapClick?: (gap: string) => void;
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
      // Go-live is always allowed; the response carries any remaining gaps.
      const res = (await goLiveSpot(spotId)) as { ready?: boolean; gaps?: string[] };
      const gaps = res.gaps ?? [];
      flash(
        res.ready === false && gaps.length > 0
          ? `Live gesetzt — es fehlen noch: ${gaps.map(gapLabel).join(", ")}`
          : "Spot ist jetzt live."
      );
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
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
    } finally {
      setBusy(false);
    }
  };

  const onTriggerEra5 = () =>
    runStatus(() => triggerEra5(spotId), "Klimatologie neu angestoßen.");

  const overrideKeys = overrides ? Object.keys(overrides) : [];
  const era5Status = era5?.status ?? "none";
  const rank = effectiveRank(readiness?.gaps ?? [], rankOverride);

  return (
    <div className="rounded-lg border border-admin-border bg-admin-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-ui font-semibold text-admin-fg">Betrieb &amp; Veröffentlichung</h2>
        {readiness && (
          <Badge tone={readiness.ready ? "success" : "neutral"}>
            {readiness.ready ? "Bereit" : "Angaben offen"} · {statusLabel(readiness.status)}
          </Badge>
        )}
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

      {/* Fertigstellen-Rang — „Auto" folgt den offenen Punkten; eine Farbe pinnt
          den Rang manuell (dieselbe Steuerung wie in der Übersichtsliste). */}
      <div className="mt-4 rounded-md border border-admin-border bg-admin-bg px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-2 text-label text-admin-muted">
            <span className={`h-2 w-2 rounded-full ${RANK_DOT[rank]}`} />
            Fertigstellen-Rang
          </span>
          <span className="text-label font-medium text-admin-fg">
            {RANK_LABEL[rank]}
            {rankOverride === null && (
              <span className="ml-1 text-caption font-normal text-admin-faint">(auto)</span>
            )}
          </span>
        </div>
        <div className="mt-2.5">
          <RankControl value={rankOverride} effective={rank} onChange={onRankChange} busy={busy} />
        </div>
      </div>

      {notice && (
        <div className="mt-3 rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label font-medium text-admin-success">
          {notice}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mt-3 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
        >
          {error}
        </div>
      )}

      {readiness && !readiness.ready && (
        <div className="mt-3 text-label text-admin-muted">
          <span className="align-middle">Fehlt noch: </span>
          {readiness.gaps.length === 0 ? (
            "—"
          ) : (
            <span className="inline-flex flex-wrap gap-1.5 align-middle">
              {readiness.gaps.map((g) =>
                onGapClick ? (
                  <button
                    key={g}
                    type="button"
                    onClick={() => onGapClick(g)}
                    className="rounded-md border border-admin-warning-bg bg-admin-warning-bg px-2 py-0.5 text-caption font-medium text-admin-warning transition-colors hover:brightness-110"
                  >
                    {gapLabel(g)}
                  </button>
                ) : (
                  <span key={g}>{gapLabel(g)}</span>
                )
              )}
            </span>
          )}
          <p className="mt-1.5 text-caption text-admin-faint">
            Veröffentlichen ist trotzdem möglich — die fehlenden Angaben sind nur
            ein Hinweis.
          </p>
        </div>
      )}

      {/* Klimatologie (ERA5) — background job; status + manual re-trigger. */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-admin-border pt-4">
        <span className="text-label text-admin-muted">
          Klimatologie:{" "}
          <span className="font-medium text-admin-fg2">
            {ERA5_LABEL[era5Status] ?? era5Status}
          </span>
        </span>
        <button
          type="button"
          disabled={busy || era5Status === "queued" || era5Status === "processing"}
          onClick={onTriggerEra5}
          className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
        >
          Neu berechnen
        </button>
      </div>

      {/* Lifecycle actions — the single place a spot goes live / offline /
          archived / reactivated (the list only links here via „Bearbeiten"). */}
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-admin-border pt-4">
        {readiness?.status === "archived" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              runStatus(() => reactivateSpot(spotId), "Spot ist wieder ein Entwurf.")
            }
            className="rounded-md bg-admin-primary px-4 py-2 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
          >
            Reaktivieren
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={busy || readiness?.status === "published"}
              onClick={onGoLive}
              className="rounded-md bg-admin-primary px-4 py-2 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
            >
              {readiness?.status === "published" ? "Live" : "Go-Live"}
            </button>
            {readiness?.status === "published" && (
              <button
                type="button"
                disabled={busy}
                onClick={() => runStatus(() => unpublishSpot(spotId), "Spot ist offline.")}
                className="rounded-md border border-admin-border bg-admin-surface px-4 py-2 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
              >
                Offline nehmen
              </button>
            )}
            <button
              type="button"
              disabled={busy || pendingArchive}
              onClick={() => setPendingArchive(true)}
              className="rounded-md border border-admin-border bg-admin-surface px-4 py-2 text-label font-medium text-admin-muted transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
            >
              Archivieren
            </button>
          </>
        )}
      </div>

      {overrideKeys.length > 0 && (
        <div className="mt-4 border-t border-admin-border pt-4">
          <p className="text-label font-semibold text-admin-fg">
            Überschriebene Felder
          </p>
          <ul className="mt-2 space-y-1.5">
            {overrideKeys.map((k) => (
              <li key={k} className="flex items-center gap-2 text-label text-admin-fg2">
                <span className="admin-mono font-medium">{k}</span>
                <span className="admin-mono text-admin-muted">= {JSON.stringify(overrides?.[k])}</span>
                <Badge tone="neutral" dot={false}>überschrieben</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
