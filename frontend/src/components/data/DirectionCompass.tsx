import { motion, useReducedMotion } from "framer-motion";
import type { LiveConditionsRead } from "../../lib/api";
import { degreesToCompass, resolveDirectionSnapshot, type DirectionSnapshot } from "../../lib/directionSnapshot";
import { formatWind, useSpotDataScope, windUnitLabel, type SportMode, type WindUnit } from "../../state/SpotDataScope";

const CLASS_LABEL = {
  onshore: "Onshore", cross_onshore: "Cross-onshore", sideshore: "Sideshore",
  cross_offshore: "Cross-offshore", offshore: "Offshore", unavailable: null,
} as const;
const KIND_LABEL = { forecast: "Forecast", nowcast: "Nowcast", measurement: "Messung" } as const;

function DirectionMark({ degrees, kind, reduced }: { degrees: number; kind: "wind" | "wave"; reduced: boolean }) {
  return <motion.g
    initial={false}
    animate={{ rotate: degrees }}
    transition={{ duration: reduced ? 0 : 0.42, ease: [0.16, 1, 0.3, 1] }}
    style={{ transformOrigin: "100px 100px" }}
    className={kind === "wind" ? "text-ink" : "text-teal"}
  >
    <path d="M100 21 L100 86" fill="none" stroke="currentColor" strokeWidth={kind === "wind" ? 5 : 4} strokeLinecap="round" strokeDasharray={kind === "wave" ? "7 6" : undefined}/>
    <path d="M91 73 L100 89 L109 73" fill={kind === "wind" ? "currentColor" : "var(--sw-surface)"} stroke="currentColor" strokeWidth="3" strokeLinejoin="round"/>
  </motion.g>;
}

function CompassGraphic({ snapshot, primary }: { snapshot: DirectionSnapshot; primary: "wind" | "wave" }) {
  const reduced = useReducedMotion() === true;
  const wind = snapshot.windDirectionFromDeg;
  const wave = snapshot.waveDirectionFromDeg;
  const coast = snapshot.coastalNormalDeg;
  const primaryDeg = primary === "wind" ? wind : wave;
  const primaryName = primary === "wind" ? "Wind" : "Welle";
  const classification = primary === "wind" ? snapshot.windCoastalClassification : snapshot.waveCoastalClassification;
  const aria = [
    `${primaryName}${primaryDeg == null ? "richtung nicht verfügbar" : ` aus ${degreesToCompass(primaryDeg)}, ${primaryDeg.toFixed(0)} Grad`}`,
    snapshot.localLabel, KIND_LABEL[snapshot.kind],
    primaryDeg == null ? "Anströmung nicht verfügbar" : classification && classification !== "unavailable" ? CLASS_LABEL[classification] : "Küstenbezug nicht verfügbar",
    primary === "wind" && wave != null ? `Welle aus ${degreesToCompass(wave)}, ${wave.toFixed(0)} Grad` : null,
    primary === "wave" && wind != null ? `Wind aus ${degreesToCompass(wind)}, ${wind.toFixed(0)} Grad` : null,
  ].filter(Boolean).join(". ");
  return <svg role="img" aria-label={aria} viewBox="0 0 200 200" className="h-auto w-full max-w-[280px] text-ink">
    <circle cx="100" cy="100" r="82" fill="var(--sw-surface)" stroke="var(--sw-line)" strokeWidth="2"/>
    <circle cx="100" cy="100" r="58" fill="none" stroke="var(--sw-line-soft)"/>
    {[["N",100,12],["O",188,100],["S",100,188],["W",12,100]].map(([label,x,y]) => <text key={label} x={x} y={y} textAnchor="middle" dominantBaseline="central" fill="currentColor" fontSize="12" fontWeight={label === "N" ? 700 : 500}>{label}</text>)}
    {coast != null && <g transform={`rotate(${coast} 100 100)`} className="text-muted"><path d="M32 100 H168" stroke="currentColor" strokeWidth="3"/><path d="M100 100 V55" stroke="currentColor" strokeWidth="2" strokeDasharray="3 4"/><path d="M94 63 L100 53 L106 63" fill="none" stroke="currentColor" strokeWidth="2"/></g>}
    {wave != null && <DirectionMark degrees={wave} kind="wave" reduced={reduced}/>} 
    {wind != null && <DirectionMark degrees={wind} kind="wind" reduced={reduced}/>} 
    <circle cx="100" cy="100" r="6" fill="var(--sw-surface)" stroke="currentColor" strokeWidth="3"/>
  </svg>;
}

export default function DirectionCompass({ live }: { live?: LiveConditionsRead | null }) {
  const { selectedForecast, forecastTimezone, forecastStale, forecastModel, sportMode, windUnit } = useSpotDataScope();
  const snapshot = resolveDirectionSnapshot({ selectedForecast, live, forecastTimezone, forecastStale, forecastModel });
  return <DirectionCompassView snapshot={snapshot} sportMode={sportMode} windUnit={windUnit}/>;
}

export function DirectionCompassView({ snapshot, sportMode, windUnit }: { snapshot: DirectionSnapshot | null; sportMode: SportMode; windUnit: WindUnit }) {
  const primary = sportMode === "surf" ? "wave" : "wind";
  const direction = snapshot ? (primary === "wind" ? snapshot.windDirectionFromDeg : snapshot.waveDirectionFromDeg) : null;
  const classification = snapshot ? (primary === "wind" ? snapshot.windCoastalClassification : snapshot.waveCoastalClassification) : null;
  const classLabel = direction != null && classification && classification !== "unavailable" ? CLASS_LABEL[classification] : null;
  return <section data-forecast-utc={snapshot?.kind === "forecast" ? snapshot.validAtUtc : ""} data-observation-type={snapshot?.kind ?? "unavailable"} aria-labelledby="direction-heading" className="min-w-0 p-4 sm:p-5">
    <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line-soft pb-4">
      <div><h2 id="direction-heading" className="text-title font-semibold text-ink">Richtung &amp; Anströmung</h2><p className="mt-1 text-label text-muted">{snapshot?.localLabel ?? "Kein gültiger Zeitpunkt"}</p></div>
      {snapshot && <div className="flex flex-wrap justify-end gap-2 text-caption"><span className="rounded-full border border-line px-2.5 py-1 font-medium text-ink">{KIND_LABEL[snapshot.kind]}</span>{snapshot.stale && <span className="rounded-full border border-orange/50 bg-orange/10 px-2.5 py-1 font-medium text-ink">Letzter Stand</span>}{snapshot.quality && <span className="rounded-full border border-line px-2.5 py-1 text-muted">Qualität: {snapshot.quality}</span>}</div>}
    </header>
    {!snapshot ? <div className="py-12 text-center"><p className="font-medium text-ink">Richtungsdaten nicht verfügbar</p><p className="mt-1 text-label text-muted">Es liegt weder ein Forecastzeitpunkt noch ein vollständiger Nowcast vor.</p></div> : <div className="grid min-w-0 gap-5 pt-5 sm:grid-cols-[minmax(0,1fr)_minmax(210px,280px)] sm:items-center">
      <div className="min-w-0">
        <p className="text-caption font-medium uppercase tracking-wider text-muted">{primary === "wind" ? "Wind kommt aus" : "Welle kommt aus"}</p>
        {direction == null ? <p className="mt-2 text-body font-semibold text-ink">{primary === "wind" ? "Windrichtung" : "Wellenrichtung"} nicht verfügbar</p> : <><p className="mt-2 text-[clamp(2rem,8vw,3.5rem)] font-semibold leading-none text-ink">Aus {degreesToCompass(direction)}</p><p className="mt-2 text-title tabular-nums text-muted">{direction.toFixed(0)}°</p></>}
        <p className="mt-4 text-body text-ink">{primary === "wind" ? `${snapshot.windKt == null ? "Windstärke nicht verfügbar" : `${formatWind(snapshot.windKt, windUnit)} ${windUnitLabel(windUnit)}`}${snapshot.gustKt == null ? "" : ` · Böen ${formatWind(snapshot.gustKt, windUnit)} ${windUnitLabel(windUnit)}`}` : `${snapshot.waveHeightM == null ? "Wellenhöhe nicht verfügbar" : `${snapshot.waveHeightM.toFixed(1)} m`}${snapshot.wavePeriodS == null ? "" : ` · ${snapshot.wavePeriodS.toFixed(0)} s`}`}</p>
        <p className="mt-2 font-medium text-ink">{direction == null ? "Anströmung nicht verfügbar" : snapshot.coastalNormalDeg == null || !classLabel ? "Küstenbezug nicht verfügbar" : classLabel}</p>
        <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-label text-muted" aria-label="Legende">
          {snapshot.windDirectionFromDeg != null && <span className="inline-flex items-center gap-2"><span className="h-0 w-7 border-t-[3px] border-ink"/>Wind</span>}
          {snapshot.waveDirectionFromDeg != null && <span className="inline-flex items-center gap-2"><span className="h-0 w-7 border-t-[3px] border-dashed border-teal"/>Welle</span>}
          {snapshot.coastalNormalDeg != null && <span className="inline-flex items-center gap-2"><span className="h-0 w-7 border-t-2 border-muted"/>Küstennormale</span>}
        </div>
      </div>
      <CompassGraphic snapshot={snapshot} primary={primary}/>
    </div>}
  </section>;
}
