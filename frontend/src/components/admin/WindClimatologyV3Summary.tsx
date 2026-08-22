import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getV3Status, type V3Status } from "../../lib/api";
import { Badge, type BadgeTone } from "./ui";

const labels:Record<string,[string,BadgeTone]>={not_calculated:["Nicht berechnet","neutral"],pending:["Ausstehend","info"],processing:["Wird berechnet","info"],refresh_pending:["Aktualisierung ausstehend","info"],refresh_processing:["Aktualisierung läuft – alte Version aktiv","info"],complete:["Vollständig","success"],limited:["Eingeschränkte Qualität","warning"],failed_active_preserved:["Refresh fehlgeschlagen – alte Version aktiv","danger"],failed_no_active:["Fehlgeschlagen – keine aktive Version","danger"],stale:["Veraltet","warning"]};
export default function WindClimatologyV3Summary({spotId}:{spotId:string}) {
  const [data,setData]=useState<V3Status|null>(null); const [failed,setFailed]=useState(false);
  useEffect(()=>{getV3Status(spotId).then(setData).catch(()=>setFailed(true))},[spotId]);
  const label=labels[data?.state??"not_calculated"]??[data?.state??"Unbekannt","neutral" as BadgeTone];
  return <section className="rounded-lg border border-admin-border bg-admin-surface p-4" aria-labelledby="v3-summary-title"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="v3-summary-title" className="text-label font-semibold">Windklimatologie V3</h2><p className="mt-1 text-caption text-admin-muted">Shadow-Verwaltung; ohne öffentliche Wirkung.</p></div>{!failed&&<Badge tone={label[1]}>{data?label[0]:"Lädt …"}</Badge>}</div>
    {failed?<p role="alert" className="mt-3 text-label text-admin-danger">V3-Status konnte nicht geladen werden.</p>:data&&<dl className="mt-3 grid gap-2 text-caption sm:grid-cols-2 xl:grid-cols-1"><div><dt className="text-admin-muted">Zeitraum / Algorithmus</dt><dd>{data.active?.period.join("–")??"—"} · <span className="admin-mono">{data.active?.algorithm_version??"—"}</span></dd></div><div><dt className="text-admin-muted">Raster</dt><dd>{data.cell?.mode==="manual"?"Manuell":"Automatisch"} · {data.cell?.actual?.join(", ")??"noch offen"}</dd></div><div><dt className="text-admin-muted">Richtungen</dt><dd>{data.directions.reviewed?"Freigegeben":"Keine freigegebenen Windrichtungen"}</dd></div><div><dt className="text-admin-muted">Letzter Erfolg</dt><dd>{data.active?.completed_at?new Date(data.active.completed_at).toLocaleDateString("de-DE"):"—"}</dd></div></dl>}
    <Link to={`/admin/spot/${spotId}/wind-climatology-v3`} className="mt-4 inline-flex min-h-9 items-center rounded-md border border-admin-border px-3 text-label font-medium text-admin-fg2 hover:bg-admin-hover">V3 verwalten</Link></section>;
}
