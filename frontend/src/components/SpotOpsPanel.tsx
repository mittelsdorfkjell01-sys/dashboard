// Operations panel for a saved spot: readiness + go-live / offline / archive, and
// a read-only view of active overrides. Embedded in AdminSpotForm in edit mode.
// ERA5/climatology runs fully in the background (no manual control here).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  archiveSpot,
  getReadiness,
  getSpot,
  goLiveSpot,
  unpublishSpot,
  type Readiness,
} from "../lib/api";
import { gapLabel, statusLabel } from "../lib/labels";

export default function SpotOpsPanel({ spotId }: { spotId: string }) {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [overrides, setOverrides] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [r, spot] = await Promise.all([
      getReadiness(spotId).catch(() => null),
      getSpot(spotId).catch(() => null),
    ]);
    setReadiness(r);
    setOverrides(spot?.overrides ?? null);
  }, [spotId]);

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
      await goLiveSpot(spotId);
      flash("Spot ist jetzt live.");
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = (e.detail as { detail?: { gaps?: string[] } } | null)?.detail;
        setError(
          `Noch nicht bereit. Fehlt: ${(detail?.gaps ?? []).map(gapLabel).join(", ")}`
        );
      } else {
        setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
      }
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

  const overrideKeys = overrides ? Object.keys(overrides) : [];

  return (
    <div className="mt-6 rounded-2xl border border-line bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[15px] font-semibold text-ink">Betrieb & Veröffentlichung</h2>
        {readiness && (
          <span
            className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${
              readiness.ready ? "text-green" : "text-muted"
            }`}
          >
            {readiness.ready ? "● Bereit" : "○ Angaben offen"} ·{" "}
            {statusLabel(readiness.status)}
          </span>
        )}
      </div>

      {notice && (
        <div className="mt-3 rounded-xl bg-green/10 px-3 py-2 text-[13px] font-medium text-green">
          {notice}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-[13px] font-medium text-red-700"
        >
          {error}
        </div>
      )}

      {readiness && !readiness.ready && (
        <p className="mt-3 text-[13px] text-muted">
          Fehlt noch: {readiness.gaps.map(gapLabel).join(", ") || "—"}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy || readiness?.status === "published"}
          onClick={onGoLive}
          className="rounded-xl bg-green px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {readiness?.status === "published" ? "Live" : "Go-Live"}
        </button>
        {readiness?.status === "published" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => runStatus(() => unpublishSpot(spotId), "Spot ist offline.")}
            className="rounded-xl border border-teal/30 px-4 py-2 text-[13px] font-medium text-teal hover:bg-teal/5 disabled:opacity-50"
          >
            Offline nehmen
          </button>
        )}
        {readiness?.status !== "archived" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => runStatus(() => archiveSpot(spotId), "Spot archiviert.")}
            className="rounded-xl border border-line px-4 py-2 text-[13px] font-medium text-muted hover:bg-teal/5 disabled:opacity-50"
          >
            Archivieren
          </button>
        )}
      </div>

      {overrideKeys.length > 0 && (
        <div className="mt-4">
          <p className="text-[13px] font-semibold text-ink">
            Überschriebene Felder
          </p>
          <ul className="mt-1.5 space-y-1">
            {overrideKeys.map((k) => (
              <li key={k} className="text-[13px] text-ink-soft">
                <span className="font-medium">{k}</span>{" "}
                <span className="text-muted">= {JSON.stringify(overrides?.[k])}</span>{" "}
                <span className="rounded-2xl bg-ink/5 px-2 py-0.5 text-[11px] text-muted">
                  überschrieben
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
