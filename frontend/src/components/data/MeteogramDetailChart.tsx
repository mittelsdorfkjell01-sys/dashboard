import { useRef, type RefObject, type UIEventHandler } from "react";
import type { WeatherCondition } from "../../lib/api";
import type { NormalizedForecastHour } from "../../lib/forecastNormalization";
import { windColor } from "../../lib/windScale";
import { formatWind, type WindUnit } from "../../state/SpotDataScope";
import type { ChartScale, MeteogramModel } from "./meteogramModel";
import { hasValidSpread } from "./meteogramModel";

const SLOT = 44;
const BAR = 20;
const ROW = {
  header: { top: 0, bottom: 46 }, weather: { top: 46, bottom: 88 },
  precipitation: { top: 88, bottom: 174 }, temperature: { top: 174, bottom: 278 },
  wind: { top: 278, bottom: 414 }, direction: { top: 414, bottom: 458 },
  wave: { top: 458, bottom: 552 }, period: { top: 552, bottom: 622 },
  time: { top: 622, bottom: 676 },
};
const WITHOUT_MARINE_HEIGHT = 512;

type Props = {
  model: MeteogramModel;
  selectedAtUtc: string | null;
  setSelectedAtUtc: (instant: string) => void;
  windUnit: WindUnit;
  scrollRef?: RefObject<HTMLDivElement>;
  onScroll?: UIEventHandler<HTMLDivElement>;
  showScrollCue?: boolean;
};

const x = (index: number) => index * SLOT + SLOT / 2;
const y = (value: number, scale: ChartScale, top: number, bottom: number) => bottom - ((value - scale.min) / Math.max(1e-9, scale.max - scale.min)) * (bottom - top);
const number = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1);
const windAxisScale = (scale: ChartScale, unit: WindUnit): ChartScale => unit === "kts" ? scale : ({ min: scale.min * 0.514444, mid: scale.mid * 0.514444, max: scale.max * 0.514444 });
const dayLabel = (date: string) => new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));

function AxisTicks({ scale }: { scale: ChartScale }) {
  return <span className="flex h-full flex-col justify-between text-xs font-medium tabular-nums text-muted"><span>{number(scale.max)}</span><span>{number(scale.mid)}</span><span>{number(scale.min)}</span></span>;
}

function AxisRow({ label, unit, scale, className = "" }: { label: string; unit?: string; scale?: ChartScale; className?: string }) {
  return <div className={`flex min-h-0 justify-between gap-2 border-b border-line px-3 py-2 ${className}`}>
    <span className="text-xs font-semibold leading-tight text-ink">{label}{unit&&<small className="mt-0.5 block font-normal text-muted">{unit}</small>}</span>
    {scale&&<AxisTicks scale={scale}/>} 
  </div>;
}

function Guides({ scale, top, bottom, width }: { scale: ChartScale; top: number; bottom: number; width: number }) {
  return <>{[scale.max,scale.mid,scale.min].map((value)=><line key={value} x1={0} x2={width} y1={y(value,scale,top,bottom)} y2={y(value,scale,top,bottom)} stroke="var(--sw-line)" strokeWidth={0.9} strokeDasharray={value===scale.min?undefined:"4 4"}/>)}</>;
}

function WeatherGlyph({ hour, cx }: { hour: NormalizedForecastHour; cx: number }) {
  const condition: WeatherCondition = hour.weather_condition ?? "unknown";
  const wet=["drizzle","rain","rain_showers"].includes(condition), snow=["snow","snow_showers"].includes(condition), storm=condition==="thunderstorm", fog=condition==="fog";
  if(condition==="unknown")return <Missing x={cx} y={(ROW.weather.top+ROW.weather.bottom)/2}/>;
  if(condition==="clear"||condition==="mainly_clear")return <g transform={`translate(${cx},67)`} fill="none" stroke="var(--sw-orange)" strokeWidth={1.5}>{hour.is_day===false?<path d="M3-7a8 8 0 1 0 5 11A7 7 0 0 1 3-7Z"/>:<><circle r={5}/><path d="M0-10v3m0 14v3M-10 0h3m14 0h3M-7-7l2 2m10 10 2 2M7-7 5-5m-10 10-2 2"/></>}</g>;
  return <g transform={`translate(${cx},67)`} fill="none" stroke="var(--sw-blue)" strokeWidth={1.5}><path d="M-8 2H6a5 5 0 0 0 0-10 7 7 0 0 0-12 2A4 4 0 0 0-8 2Z"/>{wet&&<path d="m-4 6-1 4m6-4-1 4m6-4-1 4"/>}{snow&&<path d="M-4 6v4m-2-2h4M4 6v4M2 8h4"/>}{storm&&<path d="m3 3-4 5h3l-2 5"/>}{fog&&<path d="M-6 6h11M-4 10h10"/>}</g>;
}

function Missing({ x: cx, y: cy }: { x: number; y: number }) { return <g><line x1={cx-6} x2={cx+6} y1={cy} y2={cy} stroke="var(--sw-muted)" strokeWidth={1.5}/><line x1={cx-5} x2={cx+5} y1={cy-3} y2={cy+3} stroke="var(--sw-line)" strokeWidth={0.8}/></g>; }

function TemperaturePaths({ model }: { model: MeteogramModel }) {
  const index = new Map(model.slots.map((slot,i)=>[slot.utcKey,i]));
  return <>{model.temperatureSegments.map((segment,segmentIndex)=>{const path=segment.map((hour,i)=>`${i?"L":"M"} ${x(index.get(hour.utcKey)??0)} ${y(hour.air!,model.scales.temperature,ROW.temperature.top+10,ROW.temperature.bottom-10)}`).join(" ");return <path key={segmentIndex} d={path} fill="none" stroke="var(--sw-orange)" strokeWidth={2.2} strokeLinejoin="round"/>;})}</>;
}

function WindSlot({ hour, index, scale }: { hour: NormalizedForecastHour; index: number; scale: ChartScale }) {
  const cx=x(index), bottom=ROW.wind.bottom-10;
  if(hour.wind==null)return <Missing x={cx} y={(ROW.wind.top+ROW.wind.bottom)/2}/>;
  const meanTop=y(hour.wind,scale,ROW.wind.top+10,bottom), color=windColor(hour.wind);
  const gustTop=hour.gust==null?meanTop:y(hour.gust,scale,ROW.wind.top+10,bottom);
  return <g>
    {hasValidSpread(hour)&&<rect x={cx-BAR/2-4} y={y(hour.wind_spread!.high!,scale,ROW.wind.top+10,bottom)} width={BAR+8} height={Math.max(2,y(hour.wind_spread!.low!,scale,ROW.wind.top+10,bottom)-y(hour.wind_spread!.high!,scale,ROW.wind.top+10,bottom))} rx={3} fill="var(--sw-ink-soft)" opacity={0.16}/>} 
    {hour.gust!=null&&hour.gust>hour.wind&&<rect x={cx-BAR/2} y={gustTop} width={BAR} height={meanTop-gustTop} rx={2} fill={color} opacity={0.28} stroke={color} strokeWidth={1}/>} 
    <rect x={cx-BAR/2} y={meanTop} width={BAR} height={bottom-meanTop} rx={2} fill={color}/>
    <text x={cx} y={Math.min(bottom-4,meanTop+13)} textAnchor="middle" fontSize={12} fontWeight={600} fill={hour.wind>=13?"white":"var(--sw-ink)"}>{Math.round(hour.wind)}</text>
  </g>;
}

function DirectionArrow({ hour, index }: { hour: NormalizedForecastHour; index: number }) {
  if(hour.dir==null)return <Missing x={x(index)} y={(ROW.direction.top+ROW.direction.bottom)/2}/>;
  return <g transform={`translate(${x(index)},${(ROW.direction.top+ROW.direction.bottom)/2}) rotate(${hour.dir})`}><line x1={0} y1={-10} x2={0} y2={9} stroke="var(--sw-ink-soft)" strokeWidth={1.5}/><path d="m-4 4 4 5 4-5" fill="none" stroke="var(--sw-ink-soft)" strokeWidth={1.5}/></g>;
}

export default function MeteogramDetailChart({ model, selectedAtUtc, setSelectedAtUtc, windUnit, scrollRef, onScroll, showScrollCue=false }: Props) {
  const width=Math.max(SLOT,model.slots.length*SLOT), selected=model.slots.findIndex((slot)=>slot.utcKey===selectedAtUtc);
  const displayedWindScale=windAxisScale(model.scales.wind,windUnit);
  const hitRefs=useRef<(SVGRectElement|null)[]>([]);
  const focusSlot=(index:number)=>{const target=hitRefs.current[index];if(target){target.focus();setSelectedAtUtc(model.slots[index].utcKey);}};
  return <div className="grid min-w-0 grid-cols-[104px_minmax(0,1fr)] border-y border-line bg-surface sm:grid-cols-[112px_minmax(0,1fr)]">
    <div className="grid" style={{gridTemplateRows:`46px 42px 86px 104px 136px 44px ${model.showMarine?"94px 70px":"0px 0px"} 54px`}}>
      <AxisRow label="Tag" className="bg-band/50"/><AxisRow label="Wetter"/><AxisRow label="Niederschlag" unit="mm/h · dynamisch" scale={model.scales.precipitation}/><AxisRow label="Temperatur" unit="°C · dynamisch" scale={model.scales.temperature}/><AxisRow label="Wind" unit={`${windUnit === "ms" ? "m/s" : "kt"} · dynamisch`} scale={displayedWindScale}/><AxisRow label="Windrichtung" unit="kommt aus"/>
      {model.showMarine&&<><AxisRow label="Wellenhöhe" unit="m · dynamisch" scale={model.scales.wave}/><AxisRow label="Periode" unit="s" scale={model.scales.period}/></>}
      <AxisRow label="Ortszeit"/>
    </div>
    <div ref={scrollRef} onScroll={onScroll} role="region" className={`meteogram-scroll snap-x snap-mandatory overflow-x-auto overflow-y-hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal ${showScrollCue?"meteogram-scroll--more":""}`} tabIndex={0} aria-label="Stündliches Meteogramm. Seitlich scrollen oder die Navigationsschalter verwenden.">
      <div className="relative" style={{width}}>{model.dayGroups.map((group)=><span key={`snap-${group.date}`} aria-hidden className="pointer-events-none absolute top-0 h-px w-px scroll-ml-1 snap-start" style={{left:group.start*SLOT}}/>)}<svg aria-hidden="true" focusable="false" viewBox={`0 0 ${width} ${model.showMarine?ROW.time.bottom:WITHOUT_MARINE_HEIGHT}`} className="block w-full" style={{height:model.showMarine?ROW.time.bottom:WITHOUT_MARINE_HEIGHT}}>
        {model.dayGroups.map((group)=><g key={group.date}><rect x={group.start*SLOT} y={ROW.header.top} width={group.count*SLOT} height={ROW.header.bottom} fill="var(--sw-band)" opacity={0.5}/><text x={(group.start+group.count/2)*SLOT} y={18} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--sw-ink)">{dayLabel(group.date)}</text><text x={(group.start+group.count/2)*SLOT} y={36} textAnchor="middle" fontSize={12} fill="var(--sw-muted)">Sicherheit {group.confidence??"nicht verfügbar"}{group.confidenceSource==="calendar"?" *":""}<title>{group.confidenceSource==="calendar"?"Grob geschätzt: zu wenige Modelle für eine echte Streubreite an diesem Tag.":"Aus der tatsächlichen Modellspanne berechnet."}</title></text><line x1={group.start*SLOT} x2={group.start*SLOT} y1={0} y2={model.showMarine?ROW.time.bottom:WITHOUT_MARINE_HEIGHT} stroke="var(--sw-line)" strokeWidth={1.2}/></g>)}
        <Guides scale={model.scales.precipitation} top={ROW.precipitation.top+10} bottom={ROW.precipitation.bottom-10} width={width}/><Guides scale={model.scales.temperature} top={ROW.temperature.top+10} bottom={ROW.temperature.bottom-10} width={width}/><Guides scale={model.scales.wind} top={ROW.wind.top+10} bottom={ROW.wind.bottom-10} width={width}/>
        {model.showMarine&&<><Guides scale={model.scales.wave} top={ROW.wave.top+10} bottom={ROW.wave.bottom-10} width={width}/><Guides scale={model.scales.period} top={ROW.period.top+10} bottom={ROW.period.bottom-10} width={width}/></>}
        {model.slots.map((hour,index)=><WeatherGlyph key={`weather-${hour.utcKey}`} hour={hour} cx={x(index)}/>)}
        {model.slots.map((hour,index)=>hour.precip==null?<Missing key={`rain-${hour.utcKey}`} x={x(index)} y={(ROW.precipitation.top+ROW.precipitation.bottom)/2}/>:hour.precip===0?null:<g key={`rain-${hour.utcKey}`}><rect x={x(index)-BAR/2} y={y(hour.precip,model.scales.precipitation,ROW.precipitation.top+10,ROW.precipitation.bottom-10)} width={BAR} height={ROW.precipitation.bottom-10-y(hour.precip,model.scales.precipitation,ROW.precipitation.top+10,ROW.precipitation.bottom-10)} rx={2} fill="var(--sw-blue)"/><text x={x(index)} y={y(hour.precip,model.scales.precipitation,ROW.precipitation.top+10,ROW.precipitation.bottom-10)-4} textAnchor="middle" fontSize={12} fill="var(--sw-ink)">{number(hour.precip)}</text></g>)}
        <TemperaturePaths model={model}/>{model.slots.map((hour,index)=>hour.air==null?null:<circle key={`temp-${hour.utcKey}`} cx={x(index)} cy={y(hour.air,model.scales.temperature,ROW.temperature.top+10,ROW.temperature.bottom-10)} r={2.5} fill="var(--sw-orange)"/>)}
        {model.slots.map((hour,index)=><WindSlot key={`wind-${hour.utcKey}`} hour={hour} index={index} scale={model.scales.wind}/>)}
        {model.slots.map((hour,index)=><DirectionArrow key={`dir-${hour.utcKey}`} hour={hour} index={index}/>)}
        {model.showMarine&&model.slots.map((hour,index)=>hour.swell==null?<Missing key={`wave-${hour.utcKey}`} x={x(index)} y={(ROW.wave.top+ROW.wave.bottom)/2}/>:<g key={`wave-${hour.utcKey}`}><rect x={x(index)-BAR/2} y={y(hour.swell,model.scales.wave,ROW.wave.top+10,ROW.wave.bottom-10)} width={BAR} height={ROW.wave.bottom-10-y(hour.swell,model.scales.wave,ROW.wave.top+10,ROW.wave.bottom-10)} rx={2} fill="var(--sw-teal)" opacity={0.72}/><text x={x(index)} y={ROW.wave.top+20} textAnchor="middle" fontSize={12} fill="var(--sw-ink)">{hour.swell.toFixed(1)}</text></g>)}
        {model.showMarine&&model.slots.map((hour,index)=>hour.period==null?<Missing key={`period-${hour.utcKey}`} x={x(index)} y={(ROW.period.top+ROW.period.bottom)/2}/>:<g key={`period-${hour.utcKey}`}><line x1={x(index)} x2={x(index)} y1={y(hour.period,model.scales.period,ROW.period.top+10,ROW.period.bottom-10)} y2={ROW.period.bottom-10} stroke="var(--sw-teal)" strokeWidth={2}/><circle cx={x(index)} cy={y(hour.period,model.scales.period,ROW.period.top+10,ROW.period.bottom-10)} r={3} fill="var(--sw-surface)" stroke="var(--sw-teal)" strokeWidth={2}/></g>)}
        {model.slots.map((hour,index)=><text key={`time-${hour.utcKey}`} x={x(index)} y={model.showMarine?ROW.time.top+25:500} textAnchor="middle" fontSize={12} fontWeight={hour.utcKey===selectedAtUtc?600:400} fill={hour.utcKey===selectedAtUtc?"var(--sw-ink)":"var(--sw-muted)"}>{hour.localTime}</text>)}
        {selected>=0&&<g><line x1={x(selected)} x2={x(selected)} y1={ROW.header.bottom} y2={model.showMarine?ROW.time.bottom:WITHOUT_MARINE_HEIGHT} stroke="var(--sw-orange)" strokeWidth={2} strokeDasharray="5 4"/><rect x={Math.max(0,x(selected)-40)} y={ROW.header.bottom+2} width={80} height={20} rx={4} fill="var(--sw-surface)" stroke="var(--sw-orange)"/><text x={Math.max(40,x(selected))} y={ROW.header.bottom+16} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--sw-ink)">{model.slots[selected].localTimeWithOffset}</text></g>}
        {model.slots.map((hour,index)=><rect key={`hit-${hour.utcKey}`} ref={(el)=>{hitRefs.current[index]=el;}} data-utc={hour.utcKey} tabIndex={0} role="button" aria-label={`${hour.localDate} ${hour.localTimeWithOffset} auswählen`} aria-pressed={hour.utcKey===selectedAtUtc} onClick={()=>setSelectedAtUtc(hour.utcKey)} onKeyDown={(event)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();setSelectedAtUtc(hour.utcKey);}else if(event.key==="ArrowRight"){event.preventDefault();focusSlot(Math.min(index+1,model.slots.length-1));}else if(event.key==="ArrowLeft"){event.preventDefault();focusSlot(Math.max(index-1,0));}}} className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal" x={index*SLOT} y={0} width={SLOT} height={model.showMarine?ROW.time.bottom:WITHOUT_MARINE_HEIGHT} fill="transparent"><title>{hour.localDate} {hour.localTimeWithOffset}</title></rect>)}
      </svg></div>
    </div>
  </div>;
}

export function selectedSummary(hour: NormalizedForecastHour | null, windUnit: WindUnit) {
  if(!hour)return null;
  const missing="Nicht verfügbar", unit=windUnit==="ms"?"m/s":"kt";
  const spread=hasValidSpread(hour)?`${formatWind(hour.wind_spread!.low!,windUnit)}–${formatWind(hour.wind_spread!.high!,windUnit)} ${unit}`:missing;
  const weatherLabels:Record<string,string>={clear:"Klar",mainly_clear:"Überwiegend klar",partly_cloudy:"Teilweise bewölkt",overcast:"Bedeckt",fog:"Nebel",drizzle:"Nieselregen",rain:"Regen",rain_showers:"Regenschauer",snow:"Schnee",snow_showers:"Schneeschauer",thunderstorm:"Gewitter",unknown:missing};
  return [
    ["Wetter",weatherLabels[hour.weather_condition??"unknown"]??missing],
    ["Wind",hour.wind==null?missing:`${formatWind(hour.wind,windUnit)} ${unit}`],
    ["Böe",hour.gust==null?missing:`${formatWind(hour.gust,windUnit)} ${unit}`],
    ["Modellspanne",spread],
    ["Windrichtung",hour.dir==null?missing:`${Math.round(hour.dir)}° · kommt aus`],
    ["Temperatur",hour.air==null?missing:`${number(hour.air)} °C`],
    ["Niederschlag",hour.precip==null?missing:`${number(hour.precip)} mm/h`],
    ["Wellenhöhe",hour.swell==null?missing:`${hour.swell.toFixed(1)} m`],
    ["Periode",hour.period==null?missing:`${number(hour.period)} s`],
  ] as const;
}
