import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, enqueueV3, getV3Directions, getV3Status, getV3Variant, putV3Cell, putV3Directions, type V3Directions, type V3Status, type V3Variant } from "../lib/api";
import { Badge, Button, adminFieldClass, type BadgeTone } from "../components/admin/ui";

const NAMES = ["N","NNO","NO","ONO","O","OSO","SO","SSO","S","SSW","SW","WSW","W","WNW","NW","NNW"];
const STATE: Record<string,[string,BadgeTone]> = {
  not_calculated:["Nicht berechnet","neutral"], pending:["Ausstehend","info"], processing:["Wird berechnet","info"],
  refresh_pending:["Aktualisierung ausstehend – aktive Version bleibt erhalten","info"],
  refresh_processing:["Aktualisierung läuft – aktive Version bleibt erhalten","info"], complete:["Vollständig","success"],
  limited:["Eingeschränkte Datenqualität","warning"], failed_active_preserved:["Refresh fehlgeschlagen – aktive Version bleibt erhalten","danger"],
  failed_no_active:["Fehlgeschlagen – keine aktive Version","danger"], stale:["Veraltet – Konfiguration geändert","warning"]
};
const fmt = (v:string|null|undefined) => v ? new Date(v).toLocaleString("de-DE",{dateStyle:"medium",timeStyle:"short"}) : "—";
const errorText = (e:unknown) => e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.";

export function DirectionCompass({selected,onChange}:{selected:number[];onChange:(v:number[])=>void}) {
  return <div>
    <div className="mx-auto grid max-w-[420px] grid-cols-4 gap-2" role="group" aria-label="Nutzbare meteorologische Windrichtungen">
      {NAMES.map((name,index) => { const active=selected.includes(index); const start=index*22.5, end=((index+1)*22.5)%360;
        return <button key={name} type="button" aria-pressed={active} aria-label={`${name}, Wind aus ${start} bis ${end} Grad, ${active?"ausgewählt":"nicht ausgewählt"}`}
          onClick={() => onChange(active?selected.filter(x=>x!==index):[...selected,index].sort((a,b)=>a-b))}
          className={`min-h-11 rounded-md border px-2 py-2 text-label font-semibold transition-colors ${active?"border-admin-primary bg-admin-primary-bg text-admin-primary":"border-admin-border bg-admin-surface text-admin-fg2 hover:bg-admin-hover"}`}>
          {name}<span className="block text-sz-10 font-normal opacity-80">{start}–{end}°</span>
        </button>})}
    </div>
    <p className="mt-3 text-caption text-admin-muted">Ausgewählt: {selected.length ? selected.map(i=>NAMES[i]).join(", ") : "Keine"}. Windrichtung bedeutet die Richtung, aus der der Wind kommt.</p>
  </div>;
}

export function WeekChart({data,min,max,mode}:{data:V3Variant;min:number;max:number|null;mode:"all"|"usable"}) {
  const weeks=data.variant.weeks;
  if (weeks.length!==52) return <div role="alert" className="text-admin-danger">Validierungsfehler: Erwartet wurden 52 Wochen, geliefert wurden {weeks.length}.</div>;
  return <figure aria-labelledby="v3-chart-caption">
    <figcaption id="v3-chart-caption" className="sr-only">52 ungeglättete saisonale Wochenwerte auf einer absoluten Skala von 0 bis 100 Prozent</figcaption>
    <div className="flex h-56 items-end gap-px border-b border-admin-border">
      {weeks.map((w,i) => { const value=w.reliability_percent ?? 0; return <div key={i} className="group relative flex h-full min-w-0 flex-1 items-end">
        <div tabIndex={0} role="img" aria-label={`Saisonwoche ${i+1}: ${w.reliability_percent == null?"keine veröffentlichbare Zuverlässigkeit":`${w.reliability_percent} Prozent`}`}
          className="w-full bg-admin-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-admin-fg" style={{height:`${Math.max(0,Math.min(100,value))}%`}} />
        <div className={`pointer-events-none absolute bottom-full z-10 mb-2 hidden w-56 rounded-md bg-admin-elevated p-3 text-caption shadow-admin-pop group-hover:block group-focus-within:block ${i<4?"left-0":i>47?"right-0":"left-1/2 -translate-x-1/2"}`}>
          <strong>Woche {i+1}</strong><br/>{min}–{max??"40+"} kt · {mode==="all"?"alle":"passende"} Richtungen<br/>
          Zuverlässigkeit: {w.reliability_percent??"—"}%<br/>Jahre: {w.successful_years}/{w.sample_years}<br/>
          Median Windtage: {w.median_usable_days??"—"}<br/>Median Sessionstunden: {w.median_session_hours??"—"}<br/>
          P25–P75: {String(w.p25_session_hours??"—")}–{String(w.p75_session_hours??"—")}<br/>Qualität: {String(w.quality_status??"—")}
        </div>
      </div>})}
    </div>
    <div className="mt-1 flex justify-between text-sz-10 text-admin-muted"><span>Jan</span><span>Apr</span><span>Jul</span><span>Okt</span><span>Dez</span></div>
  </figure>;
}

export default function AdminWindClimatologyV3() {
  const {spotId=""}=useParams(); const [status,setStatus]=useState<V3Status|null>(null); const [dirs,setDirs]=useState<V3Directions|null>(null);
  const [selected,setSelected]=useState<number[]>([]); const [reviewed,setReviewed]=useState(false); const [mode,setMode]=useState<"automatic"|"manual">("automatic");
  const [lat,setLat]=useState(""); const [lon,setLon]=useState(""); const [min,setMin]=useState(15); const [max,setMax]=useState<number|null>(20);
  const [directionMode,setDirectionMode]=useState<"all"|"usable">("all"); const [variant,setVariant]=useState<V3Variant|null>(null);
  const [allComparison,setAllComparison]=useState<V3Variant|null>(null);
  const [busy,setBusy]=useState<string|null>(null); const [message,setMessage]=useState<string|null>(null);
  const load=useCallback(async()=>{try{const [s,d]=await Promise.all([getV3Status(spotId),getV3Directions(spotId)]);setStatus(s);setDirs(d);setSelected(d.sectors);setReviewed(d.reviewed);setMode(s.cell?.mode??"automatic");setLat(String(s.cell?.requested[0]??""));setLon(String(s.cell?.requested[1]??""));}catch(e){setMessage(errorText(e));}},[spotId]);
  useEffect(()=>{void load();},[load]);
  useEffect(()=>{if(!status?.active)return;let cancelled=false;getV3Variant(spotId,min,max,directionMode).then(v=>{if(!cancelled)setVariant(v)}).catch(e=>{if(!cancelled){setVariant(null);setMessage(errorText(e));}});return()=>{cancelled=true}},[spotId,status?.active,min,max,directionMode]);
  useEffect(()=>{if(!status?.active||directionMode!=="usable"){setAllComparison(null);return;}getV3Variant(spotId,min,max,"all").then(setAllComparison).catch(()=>setAllComparison(null));},[spotId,status?.active,min,max,directionMode]);
  useEffect(()=>{if(!status || !["pending","processing","refresh_pending","refresh_processing"].includes(status.state))return;const timer=window.setInterval(()=>void load(),2500);return()=>window.clearInterval(timer)},[status,load]);
  const state=STATE[status?.state??"not_calculated"]??[status?.state??"Unbekannt","neutral" as BadgeTone];
  const saveDirs=async()=>{setBusy("dirs");setMessage(null);try{const result=await putV3Directions(spotId,{sectors:selected,reviewed,expected_updated_at:dirs?.updated_at});setDirs(result);setMessage(result.run?.created?"Richtungen gespeichert; V3-Lauf eingeplant.":"Richtungen gespeichert.");await load();}catch(e){setMessage(errorText(e))}finally{setBusy(null)}};
  const saveCell=async()=>{setBusy("cell");setMessage(null);try{await putV3Cell(spotId,{mode,latitude:mode==="manual"?Number(lat):null,longitude:mode==="manual"?Number(lon):null});setMessage("Rasterauswahl gespeichert; V3-Lauf eingeplant.");await load();}catch(e){setMessage(errorText(e))}finally{setBusy(null)}};
  const recalc=async()=>{if(!window.confirm("V3 für diesen Spot neu berechnen? Die aktive Version bleibt verfügbar."))return;setBusy("run");try{const r=await enqueueV3(spotId);setMessage(r.created?"V3-Lauf wurde eingeplant.":"Für diese Konfiguration läuft bereits ein Lauf oder sie ist aktuell.");await load();}catch(e){setMessage(errorText(e))}finally{setBusy(null)}};
  const invalidCompare=useMemo(()=>directionMode==="usable"&&!!variant&&!!allComparison&&variant.variant.weeks.some((week,index)=>{
    const base=allComparison.variant.weeks[index]; return (week.reliability_percent??0)>(base?.reliability_percent??0)|| (week.median_session_hours??0)>(base?.median_session_hours??0);
  }),[directionMode,variant,allComparison]);
  if(!status||!dirs)return <p role="status" className="text-admin-muted">Windklimatologie wird geladen …</p>;
  return <div className="max-w-6xl pb-12"><Link to={`/admin/spot/${spotId}/edit`} className="text-admin-primary underline">← Zurück zum Spot</Link>
    <div className="mt-4 flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">Windklimatologie V3</h1><p className="mt-1 max-w-3xl text-ui text-admin-muted">Administrative Shadow-Vorschau. Öffentlich bleibt weiterhin V2 aktiv.</p></div><Button variant="primary" onClick={recalc} disabled={busy!==null}>{busy==="run"?"Wird eingeplant …":"V3 neu berechnen"}</Button></div>
    {message&&<p role="status" className="mt-4 rounded-md border border-admin-border bg-admin-surface p-3 text-label">{message}</p>}
    <section className="mt-6 rounded-lg border border-admin-border bg-admin-surface p-4"><div className="flex flex-wrap gap-2"><Badge tone={state[1]}>{state[0]}</Badge>{status.directions.usable_available?<Badge tone="success">Richtungen freigegeben</Badge>:<Badge tone="warning">Keine freigegebenen Windrichtungen</Badge>}</div>
      <dl className="mt-4 grid gap-3 text-label sm:grid-cols-2 lg:grid-cols-4"><div><dt className="text-admin-muted">Aktiver Zeitraum</dt><dd>{status.active?.period.join("–")??"—"}</dd></div><div><dt className="text-admin-muted">Algorithmus</dt><dd className="admin-mono">{status.active?.algorithm_version??"—"}</dd></div><div><dt className="text-admin-muted">Letzter Erfolg</dt><dd>{fmt(status.active?.completed_at)}</dd></div><div><dt className="text-admin-muted">Gültige Jahre / Qualität</dt><dd>{String(status.active?.quality?.valid_years??"—")} · {String(status.active?.quality?.quality_status??"—")}</dd></div></dl>
      {status.latest?.error&&<p role="alert" className="mt-3 text-admin-danger">{status.latest.error_category??"Fehler"}: {status.latest.error}</p>}</section>
    <div className="mt-6 grid gap-6 lg:grid-cols-2"><section className="rounded-lg border border-admin-border bg-admin-surface p-4"><h2 className="text-lg font-semibold">Nutzbare Windrichtungen</h2><p className="mt-1 text-caption text-admin-muted">16 feste meteorologische Sektoren; getrennte Gruppen und Nord-Wrap sind erlaubt.</p><div className="mt-4"><DirectionCompass selected={selected} onChange={setSelected}/></div><label className="mt-4 flex min-h-11 items-center gap-2"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/> Auswahl fachlich freigeben</label><Button className="mt-3" variant="primary" onClick={saveDirs} disabled={busy!==null}>{busy==="dirs"?"Speichert …":"Richtungen speichern"}</Button></section>
      <section className="rounded-lg border border-admin-border bg-admin-surface p-4"><h2 className="text-lg font-semibold">Rasterzelle</h2><div className="mt-3 flex gap-2"><Button variant={mode==="automatic"?"primary":"secondary"} aria-pressed={mode==="automatic"} onClick={()=>setMode("automatic")}>Automatisch</Button><Button variant={mode==="manual"?"primary":"secondary"} aria-pressed={mode==="manual"} onClick={()=>setMode("manual")}>Manuell</Button></div>{mode==="manual"&&<div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-label">Latitude<input className={`${adminFieldClass} mt-1 w-full`} type="number" min={-90} max={90} step="any" value={lat} onChange={e=>setLat(e.target.value)}/></label><label className="text-label">Longitude<input className={`${adminFieldClass} mt-1 w-full`} type="number" min={-180} max={180} step="any" value={lon} onChange={e=>setLon(e.target.value)}/></label></div>}<dl className="mt-4 grid gap-2 text-label sm:grid-cols-2"><div><dt className="text-admin-muted">Spot</dt><dd className="admin-mono">{status.cell?.spot.join(", ")??"—"}</dd></div><div><dt className="text-admin-muted">Angefragt</dt><dd className="admin-mono">{status.cell?.requested.join(", ")??"—"}</dd></div><div><dt className="text-admin-muted">Tatsächliches Raster</dt><dd className="admin-mono">{status.cell?.actual?.join(", ")??"Noch nicht ermittelt"}</dd></div><div><dt className="text-admin-muted">Distanz</dt><dd>{status.cell?.distance_km==null?"—":`${status.cell.distance_km} km`}</dd></div><div><dt className="text-admin-muted">Modell / Auflösung</dt><dd>{status.cell?.model??"ERA5"} · {status.cell?.resolution_degrees??0.25}°</dd></div></dl><Button className="mt-4" variant="primary" onClick={saveCell} disabled={busy!==null}>{busy==="cell"?"Speichert …":"Raster speichern"}</Button></section></div>
    <section className="mt-6 rounded-lg border border-admin-border bg-admin-surface p-4"><h2 className="text-lg font-semibold">52-Wochen-Vorschau</h2><div className="mt-4 flex flex-wrap items-end gap-3"><label className="text-label">Untergrenze<input className={`${adminFieldClass} mt-1 w-28`} type="number" min={5} max={39} value={min} onChange={e=>setMin(Math.min(Number(e.target.value),max==null?40:max-1))}/></label><label className="text-label">Obergrenze<select className={`${adminFieldClass} mt-1 w-28`} value={max??"plus"} onChange={e=>setMax(e.target.value==="plus"?null:Number(e.target.value))}>{Array.from({length:35},(_,i)=>i+6).filter(v=>v>min).map(v=><option key={v}>{v}</option>)}<option value="plus">40+</option></select></label>{([[10,15],[15,20],[20,30],[30,null]] as Array<[number,number|null]>).map(([a,b])=><Button key={`${a}-${b}`} onClick={()=>{setMin(a);setMax(b)}}>{a}–{b??"40+"}</Button>)}<div className="flex gap-2"><Button variant={directionMode==="all"?"primary":"secondary"} onClick={()=>setDirectionMode("all")}>Alle Richtungen</Button><Button variant={directionMode==="usable"?"primary":"secondary"} disabled={!status.directions.usable_available} onClick={()=>setDirectionMode("usable")}>Passende Richtungen</Button></div></div>{invalidCompare&&<p role="alert" className="mt-3 text-admin-danger">Validierungsfehler: Der Richtungsfilter erhöht Zuverlässigkeit oder Sessionstunden; die gefilterte Vorschau wird nicht angezeigt.</p>}<div className="mt-6">{variant&&!invalidCompare?<WeekChart data={variant} min={min} max={max} mode={directionMode}/>:!invalidCompare&&<p className="text-admin-muted">Diese Variante ist nicht vorbereitet oder es existiert noch keine aktive Version.</p>}</div></section>
  </div>;
}
