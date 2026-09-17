import type { LiveConditionsRead, LiveWindAnalysis } from "./api";

export const MS_TO_KT = 1 / 0.514444;
export const VARIABLE_WIND_THRESHOLD_MS = 1.5;
export const LIVE_WIND_STALE_AFTER_MS = 45 * 60_000;

export type CurrentWindSource = "live_wind" | "model_nowcast" | "unavailable";
export type CurrentWindStatus = "station_adjusted" | "baseline" | "unavailable";
export type WindDirectionState = "known" | "variable" | "uncertain" | "unavailable";

export interface CurrentWindPresentation {
  source: CurrentWindSource;
  status: CurrentWindStatus;
  statusLabel: "Stationskorrigiert" | "Baseline" | "Nicht verfügbar";
  windKt: number | null;
  windMs: number | null;
  directionFromDeg: number | null;
  directionState: WindDirectionState;
  analyzedAt: string | null;
  validAt: string | null;
  ageMinutes: number | null;
  stationCount: number;
  uncertaintyMs: number | null;
  speedUncertaintyBandMs: [number, number] | null;
  directionUncertaintyDeg: number | null;
  confidence: number | null;
  stale: boolean;
  fallbackReason: string | null;
}

const finite = (value: number | null | undefined): value is number =>
  typeof value === "number" && Number.isFinite(value);

const validDirection = (value: number | null | undefined): value is number =>
  finite(value) && value >= 0 && value < 360;

/** Quantisation is intentional: public current-wind displays do not imply
 * sub-knot/sub-sector accuracy, and tiny refresh-to-refresh analysis changes
 * therefore do not repaint the map marker or visible number. */
export const displayWindKt = (value: number): number => Math.max(0, Math.round(value));
export const displayDirectionDeg = (value: number): number => Math.round(value / 10) * 10 % 360;

function ageMinutes(instant: string | null | undefined, nowMs: number): number | null {
  if (!instant) return null;
  const value = Date.parse(instant);
  if (!Number.isFinite(value)) return null;
  return Math.max(0, Math.floor((nowMs - value) / 60_000));
}

type AvailableLiveWind = LiveWindAnalysis & {
  status: "baseline" | "station_adjusted";
  wind_speed_ms: number;
};

function usableLiveWind(analysis: LiveWindAnalysis | null | undefined): analysis is AvailableLiveWind {
  return !!analysis
    && analysis.status !== "unavailable"
    && finite(analysis.wind_speed_ms)
    && analysis.wind_speed_ms >= 0;
}

function directionState(
  speedMs: number,
  direction: number | null | undefined,
  uncertaintyMs: number | null | undefined,
  confidence: number | null | undefined,
  directionUncertaintyDeg?: number | null,
): WindDirectionState {
  if (speedMs < VARIABLE_WIND_THRESHOLD_MS) return "variable";
  if (
    (finite(uncertaintyMs) && uncertaintyMs >= speedMs)
    || (finite(confidence) && confidence < 0.35)
    || (finite(directionUncertaintyDeg) && directionUncertaintyDeg >= 90)
  ) {
    return "uncertain";
  }
  return validDirection(direction) ? "known" : "unavailable";
}

/** Resolve the current wind product without ever using a station measurement
 * as the spot value. LiveWind wins; an unavailable/missing analysis falls back
 * only to `current`, the model nowcast. */
export function currentWindPresentation(
  live: LiveConditionsRead | null | undefined,
  nowMs = Date.now(),
): CurrentWindPresentation {
  const analysis = live?.live_wind;
  if (usableLiveWind(analysis)) {
    const state = directionState(
      analysis.wind_speed_ms,
      analysis.wind_direction_from_deg,
      analysis.uncertainty_ms,
      analysis.confidence,
      analysis.direction_uncertainty_deg,
    );
    const age = ageMinutes(analysis.analyzed_at, nowMs);
    return {
      source: "live_wind",
      status: analysis.status,
      statusLabel: analysis.status === "station_adjusted" ? "Stationskorrigiert" : "Baseline",
      windKt: displayWindKt(analysis.wind_speed_ms * MS_TO_KT),
      windMs: analysis.wind_speed_ms,
      directionFromDeg: state === "known" && validDirection(analysis.wind_direction_from_deg)
        ? displayDirectionDeg(analysis.wind_direction_from_deg)
        : null,
      directionState: state,
      analyzedAt: analysis.analyzed_at,
      validAt: analysis.valid_at,
      ageMinutes: age,
      stationCount: analysis.station_count,
      uncertaintyMs: finite(analysis.uncertainty_ms) ? analysis.uncertainty_ms : null,
      speedUncertaintyBandMs:
        finite(analysis.speed_uncertainty_band_ms?.low_ms)
        && finite(analysis.speed_uncertainty_band_ms?.high_ms)
          ? [analysis.speed_uncertainty_band_ms.low_ms, analysis.speed_uncertainty_band_ms.high_ms]
          : null,
      directionUncertaintyDeg: finite(analysis.direction_uncertainty_deg)
        ? analysis.direction_uncertainty_deg
        : null,
      confidence: finite(analysis.confidence) ? analysis.confidence : null,
      stale: age == null || age * 60_000 > LIVE_WIND_STALE_AFTER_MS || live?.provenance?.stale === true,
      fallbackReason: analysis.status === "baseline"
        ? friendlyFallbackReason(analysis.fallback_reason)
        : null,
    };
  }

  const current = live?.current;
  if (current && finite(current.wind) && current.wind >= 0) {
    const speedMs = finite(current.wind_ms) ? current.wind_ms : current.wind / MS_TO_KT;
    const state = directionState(speedMs, current.dir, null, null);
    const age = ageMinutes(live?.time, nowMs);
    return {
      source: "model_nowcast",
      status: "baseline",
      statusLabel: "Baseline",
      windKt: displayWindKt(current.wind),
      windMs: speedMs,
      directionFromDeg: state === "known" && validDirection(current.dir)
        ? displayDirectionDeg(current.dir)
        : null,
      directionState: state,
      analyzedAt: live?.time ?? null,
      validAt: live?.time ?? null,
      ageMinutes: age,
      stationCount: 0,
      uncertaintyMs: null,
      speedUncertaintyBandMs: null,
      directionUncertaintyDeg: null,
      confidence: null,
      stale: age == null || age * 60_000 > LIVE_WIND_STALE_AFTER_MS || live?.provenance?.stale === true,
      fallbackReason: friendlyFallbackReason(analysis?.fallback_reason ?? "live_wind_unavailable"),
    };
  }

  return {
    source: "unavailable",
    status: "unavailable",
    statusLabel: "Nicht verfügbar",
    windKt: null,
    windMs: null,
    directionFromDeg: null,
    directionState: "unavailable",
    analyzedAt: null,
    validAt: null,
    ageMinutes: null,
    stationCount: 0,
    uncertaintyMs: null,
    speedUncertaintyBandMs: null,
    directionUncertaintyDeg: null,
    confidence: null,
    stale: false,
    fallbackReason: friendlyFallbackReason(analysis?.fallback_reason ?? "model_baseline_unavailable"),
  };
}

const FALLBACK_MESSAGES: Record<string, string> = {
  engine_disabled: "LiveWind ist für diesen Spot noch nicht aktiviert; angezeigt wird die Modellbasis.",
  live_wind_unavailable: "LiveWind ist für diesen Spot noch nicht verfügbar; angezeigt wird der Modell-Nowcast.",
  model_baseline_unavailable: "Für diesen Spot ist derzeit auch keine belastbare Modellbasis verfügbar.",
  station_residuals_unavailable: "Es liegen keine ausreichend aktuellen Stationsresiduen vor; angezeigt wird die Modellbasis.",
  station_residual_evidence_insufficient: "Die Stationslage ist für eine Korrektur noch nicht belastbar genug; angezeigt wird die Modellbasis.",
  station_residual_conflict: "Die relevanten Stationen widersprechen sich; angezeigt wird vorsorglich die Modellbasis.",
};

export function friendlyFallbackReason(reason: string | null | undefined): string {
  const normalized = reason?.trim();
  if (!normalized) return "Die Stationskorrektur ist nicht verfügbar; angezeigt wird die Modellbasis.";
  if (FALLBACK_MESSAGES[normalized]) return FALLBACK_MESSAGES[normalized];
  if (normalized.startsWith("quality_gate:")) {
    return "Die aktuelle Analyse hat die Qualitätsprüfung nicht bestanden; angezeigt wird die Modellbasis.";
  }
  if (normalized.startsWith("operational_gate:")) {
    return "LiveWind wurde wegen eines Betriebsproblems automatisch auf die Modellbasis zurückgesetzt.";
  }
  return "LiveWind konnte für diesen Zeitpunkt nicht sicher korrigiert werden; angezeigt wird die Modellbasis.";
}

export function formatAge(minutes: number | null): string {
  if (minutes == null) return "Alter unbekannt";
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.floor(minutes / 60);
  return `vor ${hours} Std.`;
}

export function uncertaintyBandKt(presentation: CurrentWindPresentation): [number, number] | null {
  if (presentation.speedUncertaintyBandMs) {
    return [
      displayWindKt(presentation.speedUncertaintyBandMs[0] * MS_TO_KT),
      displayWindKt(presentation.speedUncertaintyBandMs[1] * MS_TO_KT),
    ];
  }
  if (presentation.windMs == null || presentation.uncertaintyMs == null) return null;
  return [
    displayWindKt(Math.max(0, presentation.windMs - presentation.uncertaintyMs) * MS_TO_KT),
    displayWindKt((presentation.windMs + presentation.uncertaintyMs) * MS_TO_KT),
  ];
}
