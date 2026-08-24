import type { MeteogramViewMode } from "./meteogramView";

type Props = {
  mode: MeteogramViewMode; dayLabel: string; canPreviousDay: boolean; canNextDay: boolean;
  canPreviousSlot: boolean; canNextSlot: boolean; onMode: (mode:MeteogramViewMode)=>void;
  onPreviousDay:()=>void; onToday:()=>void; onNextDay:()=>void; onPreviousSlot:()=>void; onNextSlot:()=>void;
};

const button="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-line bg-surface px-3 text-label font-semibold text-ink hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-not-allowed disabled:opacity-40";

export default function MeteogramControls(props:Props){
  return <div className="space-y-3" aria-label="Meteogramm-Navigation">
    <div className="flex flex-wrap items-center gap-2"><button type="button" className={button} onClick={props.onPreviousDay} disabled={!props.canPreviousDay} aria-label="Vorheriger Prognosetag">← <span className="ml-1 hidden sm:inline">Vorheriger Tag</span></button><button type="button" className={button} onClick={props.onToday}>Heute</button><button type="button" className={button} onClick={props.onNextDay} disabled={!props.canNextDay} aria-label="Nächster Prognosetag"><span className="mr-1 hidden sm:inline">Nächster Tag</span> →</button><span className="ml-auto text-label font-semibold text-ink" aria-live="polite">{props.dayLabel}</span></div>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="inline-flex rounded-md border border-line bg-band p-1" role="group" aria-label="Zeitraum anzeigen">{(["24h","48h","5d"] as const).map((mode)=><button key={mode} type="button" className={`min-h-11 rounded px-3 text-label font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal ${props.mode===mode?"bg-ink text-surface":"text-ink hover:bg-surface"}`} aria-pressed={props.mode===mode} onClick={()=>props.onMode(mode)}>{mode==="5d"?"5 Tage":mode.replace("h"," h")}</button>)}</div>
      <div className="flex gap-2" role="group" aria-label="Ausgewählten Zeitpunkt ändern"><button type="button" className={button} onClick={props.onPreviousSlot} disabled={!props.canPreviousSlot} aria-label="Vorheriger Zeitpunkt">−</button><button type="button" className={button} onClick={props.onNextSlot} disabled={!props.canNextSlot} aria-label="Nächster Zeitpunkt">+</button></div>
    </div>
  </div>;
}
