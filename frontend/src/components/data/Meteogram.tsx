import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { NormalizedForecastSeries } from "../../lib/forecastNormalization";
import { useSpotDataScope } from "../../state/SpotDataScope";
import WindScaleLegend from "../WindScaleLegend";
import ForecastDataTable from "./ForecastDataTable";
import MeteogramControls from "./MeteogramControls";
import MeteogramDetailChart, { selectedSummary } from "./MeteogramDetailChart";
import MeteogramLegend from "./MeteogramLegend";
import MeteogramTrend from "./MeteogramTrend";
import { buildMeteogramModel, marineStatusText } from "./meteogramModel";
import { closestDetailDayIndex, closestSlotOnDay, initialMeteogramView, projectMeteogramView, type MeteogramViewMode } from "./meteogramView";

const localDayLabel=(date:string)=>new Intl.DateTimeFormat("de-DE",{weekday:"long",day:"2-digit",month:"2-digit",timeZone:"UTC"}).format(new Date(`${date}T12:00:00Z`));

export default function Meteogram({ forecast, compact = false }: { forecast: NormalizedForecastSeries; compact?: boolean }) {
  const { selectedAtUtc, setSelectedAtUtc, selectedForecast, windUnit } = useSpotDataScope();
  const model = useMemo(() => buildMeteogramModel(forecast), [forecast]);
  const todayIndex=useMemo(()=>closestDetailDayIndex(model),[model]);
  const [mode,setMode]=useState<MeteogramViewMode>(initialMeteogramView);
  const [dayIndex,setDayIndex]=useState(todayIndex);
  const [tableOpen,setTableOpen]=useState(false);
  const [showScrollCue,setShowScrollCue]=useState(true);
  const [diagnosticsOpen,setDiagnosticsOpen]=useState(false);
  const scrollRef=useRef<HTMLDivElement>(null);
  const tableId=useId();
  const diagnosticsId=useId();
  const view=useMemo(()=>projectMeteogramView(model,dayIndex,mode),[model,dayIndex,mode]);
  const selectedIndex=model.slots.findIndex((slot)=>slot.utcKey===selectedAtUtc);
  const summary=selectedSummary(selectedForecast,windUnit)??[];
  const lastDetail=model.slots[model.slots.length-1];
  const activeDay=model.detailDays[dayIndex];

  useEffect(()=>setDayIndex((current)=>Math.min(current,Math.max(0,model.detailDays.length-1))),[model.detailDays.length]);
  useEffect(()=>{if(forecast.diagnostics.length&&typeof console!=="undefined")console.warn(`Meteogramm: ${forecast.diagnostics.length} Datenqualitätshinweis(e)`,forecast.diagnostics);},[forecast.diagnostics]);
  useEffect(()=>{
    const container=scrollRef.current;if(!container)return;
    const target=mode==="5d"?(model.dayGroups.find((group)=>group.date===(activeDay?.local_date??activeDay?.date))?.start??0)*44:0;
    const reduce=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    container.scrollTo({left:target,behavior:reduce?"auto":"smooth"});
    setShowScrollCue(container.scrollWidth>container.clientWidth&&target<container.scrollWidth-container.clientWidth-2);
  },[activeDay,mode,model.dayGroups]);

  if (!model.slots.length && !model.trendDays.length) return <div className="border-y border-line bg-band/40 px-4 py-5 text-ui text-muted">Für diesen Zeitraum sind keine Prognosedaten verfügbar.</div>;
  const selectOffset=(offset:number)=>{const next=model.slots[selectedIndex+offset];if(next)setSelectedAtUtc(next.utcKey);};
  const selectDay=(nextIndex:number)=>{const bounded=Math.min(Math.max(nextIndex,0),Math.max(0,model.detailDays.length-1));setDayIndex(bounded);setSelectedAtUtc(closestSlotOnDay(model,bounded,selectedAtUtc));};
  const timezoneFallback=forecast.timezoneStatus.status==="fallback_utc";

  return <section id="meteogram" data-forecast-utc={selectedForecast?.utcKey??""} aria-labelledby="meteogram-heading" className="min-w-0 overflow-hidden bg-surface">
    <div className="space-y-4 border-b border-line px-3 py-4 sm:px-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="meteogram-heading" className="text-ui font-semibold text-ink">Stundenprognose · Tage 1–5</h2><p className="mt-1 text-label text-muted">Spot-Zeitzone: <strong className="font-semibold text-ink">{forecast.timezone}</strong> · Skalen über den vollständigen Detailhorizont{forecast.calibrated&&<> · <span className="font-medium text-ink">kalibriert</span></>}</p></div><span className="rounded-full border border-line bg-band px-3 py-1 text-label font-medium text-muted">{view.slots.length} Zeitpunkte sichtbar</span></div>
      {timezoneFallback&&<p role="status" className="rounded-lg border border-line bg-band px-3 py-2 text-label text-ink">Die angegebene Spot-Zeitzone „{forecast.timezoneStatus.requested}“ ist nicht verfügbar. Zeiten werden kontrolliert in UTC gezeigt.</p>}
      {forecast.stale&&<p role="status" className="rounded-lg border border-line bg-band px-3 py-2 text-label text-ink">Forecast: letzter verfügbarer Stand. Neuere Daten werden nach Verfügbarkeit angezeigt.</p>}
      {forecast.diagnostics.length>0&&<div role="status" className="rounded-lg border border-line bg-band px-3 py-2 text-label text-ink"><button type="button" className="font-semibold underline decoration-dotted underline-offset-2" aria-expanded={diagnosticsOpen} aria-controls={diagnosticsId} onClick={()=>setDiagnosticsOpen((open)=>!open)}>{forecast.diagnostics.length} Datenqualitätshinweis{forecast.diagnostics.length===1?"":"e"} {diagnosticsOpen?"ausblenden":"anzeigen"}</button>{diagnosticsOpen&&<ul id={diagnosticsId} className="mt-2 list-disc space-y-1 pl-5 text-muted">{forecast.diagnostics.map((diagnostic,index)=><li key={index}>{diagnostic.message} <span className="text-xs">({diagnostic.path})</span></li>)}</ul>}</div>}
      <MeteogramControls mode={mode} dayLabel={activeDay?localDayLabel(activeDay.local_date??activeDay.date):"Kein Detailtag"} canPreviousDay={dayIndex>0} canNextDay={dayIndex<model.detailDays.length-1} canPreviousSlot={selectedIndex>0} canNextSlot={selectedIndex>=0&&selectedIndex<model.slots.length-1} onMode={setMode} onPreviousDay={()=>selectDay(dayIndex-1)} onToday={()=>selectDay(todayIndex)} onNextDay={()=>selectDay(dayIndex+1)} onPreviousSlot={()=>selectOffset(-1)} onNextSlot={()=>selectOffset(1)}/>
      <MeteogramLegend/>
      {!model.showMarine&&<p className="rounded-lg border border-line bg-band/60 px-3 py-2 text-label text-muted"><span className="font-semibold text-ink">Marinewerte:</span> {marineStatusText(model.marineStatus)}</p>}
      {selectedForecast&&<div className="rounded-lg border border-orange/40 bg-orange/5 px-3 py-3" aria-live="polite" aria-atomic="true"><p className="mb-2 text-label font-semibold text-ink">Auswahl · {selectedForecast.localDate} · {selectedForecast.localTimeWithOffset}</p><dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-label tabular-nums sm:flex sm:flex-wrap sm:gap-x-5">{summary.map(([label,value])=><div key={label}><dt className="text-muted">{label}</dt><dd className="font-semibold text-ink">{value}</dd></div>)}</dl></div>}
    </div>
    {view.slots.length>0&&<div className="relative"><MeteogramDetailChart model={view} selectedAtUtc={selectedAtUtc} setSelectedAtUtc={setSelectedAtUtc} windUnit={windUnit} scrollRef={scrollRef} showScrollCue={showScrollCue} onScroll={(event)=>{const node=event.currentTarget;setShowScrollCue(node.scrollLeft<node.scrollWidth-node.clientWidth-2);}}/>{showScrollCue&&<p className="pointer-events-none absolute bottom-2 right-3 rounded bg-surface/95 px-2 py-1 text-xs font-medium text-muted shadow-card" aria-hidden>Weitere Zeiten →</p>}</div>}
    {lastDetail&&<div className="border-b border-line bg-band px-3 py-3 text-label text-muted sm:px-4"><span className="font-semibold text-ink">Ende der Stundenprognose:</span> {lastDetail.localDate}, {lastDetail.localTimeWithOffset}. Danach folgen ausschließlich Tagestrends.</div>}
    <div className="border-b border-line px-3 py-3 sm:px-4"><button type="button" className="min-h-11 rounded-lg border border-line bg-surface px-4 text-label font-semibold text-ink hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal" aria-expanded={tableOpen} aria-controls={tableId} onClick={()=>setTableOpen((open)=>!open)}>Daten als Tabelle {tableOpen?"schließen":"öffnen"}</button></div>
    {tableOpen&&<div id={tableId} className="space-y-2 border-b border-line px-3 py-4 sm:px-4"><p className="text-label text-muted">Die Tabelle zeigt exakt den aktuell gewählten Diagrammausschnitt in derselben Spot-Zeitzone.</p><ForecastDataTable model={view} windUnit={windUnit}/></div>}
    {!compact&&<><div className="space-y-2 border-b border-line px-3 py-3 sm:px-4"><p className="text-label font-semibold text-ink">Windfarbskala</p><WindScaleLegend/></div><MeteogramTrend days={model.trendDays} windUnit={windUnit}/></>}
  </section>;
}
