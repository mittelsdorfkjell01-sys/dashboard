import type { NormalizedForecastHour } from "../../lib/forecastNormalization";
import { formatWind, type WindUnit } from "../../state/SpotDataScope";
import type { MeteogramModel } from "./meteogramModel";

const missing="Nicht verfügbar";
const number=(value:number|null|undefined,unit:string,digits=0)=>value==null?missing:`${value.toFixed(digits)} ${unit}`;
const weather:Record<string,string>={clear:"Klar",mainly_clear:"Überwiegend klar",partly_cloudy:"Teilweise bewölkt",overcast:"Bedeckt",fog:"Nebel",drizzle:"Nieselregen",rain:"Regen",rain_showers:"Regenschauer",snow:"Schnee",snow_showers:"Schneeschauer",thunderstorm:"Gewitter",unknown:missing};
const wind=(value:number|null|undefined,unit:WindUnit)=>value==null?missing:`${formatWind(value,unit)} ${unit==="ms"?"m/s":"kt"}`;
const spread=(hour:NormalizedForecastHour,unit:WindUnit)=>hour.wind_spread?.n&&hour.wind_spread.n>=2?`${wind(hour.wind_spread.low,unit)} bis ${wind(hour.wind_spread.high,unit)} (${hour.wind_spread.n} Modelle)`:missing;

export default function ForecastDataTable({model,windUnit}:{model:MeteogramModel;windUnit:WindUnit}){
  const confidence=new Map(model.dayGroups.map((day)=>[day.date,day.confidence]));
  return <div className="max-h-[70vh] overflow-auto rounded-lg border border-line" tabIndex={0} aria-label="Forecast-Tabelle horizontal und vertikal scrollen">
    <table className="w-full min-w-[1180px] border-collapse text-left text-label text-ink">
      <caption className="sticky left-0 bg-band px-4 py-3 text-left text-ui font-semibold">Vollständige Stundenprognose in Spot-Ortszeit</caption>
      <thead className="sticky top-0 z-10 bg-surface"><tr>{["Lokales Datum","Lokale Uhrzeit","Wetterzustand","Niederschlag","Temperatur","Mittelwind","Böe","Modellspanne","Windrichtung","Wellenhöhe","Periode","Sicherheit","Datenverfügbarkeit"].map((label)=><th key={label} scope="col" className="whitespace-nowrap border-b border-line px-3 py-3 font-semibold">{label}</th>)}</tr></thead>
      <tbody>{model.slots.map((hour)=><tr key={hour.utcKey} className="odd:bg-band/40"><th scope="row" className="whitespace-nowrap border-b border-line px-3 py-3 font-semibold">{hour.localDate}</th><td className="whitespace-nowrap border-b border-line px-3 py-3">{hour.localTimeWithOffset}</td><td className="border-b border-line px-3 py-3">{weather[hour.weather_condition??"unknown"]??missing}</td><td className="border-b border-line px-3 py-3 tabular-nums">{number(hour.precip,"mm/h",1)}</td><td className="border-b border-line px-3 py-3 tabular-nums">{number(hour.air,"°C",1)}</td><td className="border-b border-line px-3 py-3 tabular-nums">{wind(hour.wind,windUnit)}</td><td className="border-b border-line px-3 py-3 tabular-nums">{wind(hour.gust,windUnit)}</td><td className="border-b border-line px-3 py-3 tabular-nums">{spread(hour,windUnit)}</td><td className="border-b border-line px-3 py-3 tabular-nums">{hour.dir==null?missing:`${Math.round(hour.dir)}° · kommt aus`}</td><td className="border-b border-line px-3 py-3 tabular-nums">{number(hour.swell,"m",1)}</td><td className="border-b border-line px-3 py-3 tabular-nums">{number(hour.period,"s",1)}</td><td className="border-b border-line px-3 py-3">{confidence.get(hour.localDate)??missing}</td><td className="border-b border-line px-3 py-3">{availability(hour)}</td></tr>)}</tbody>
    </table>
  </div>;
}

function availability(hour:NormalizedForecastHour){
  const missingFields=[hour.weather_condition==null||hour.weather_condition==="unknown"?"Wetter":null,hour.precip==null?"Niederschlag":null,hour.air==null?"Temperatur":null,hour.wind==null?"Wind":null,hour.gust==null?"Böe":null,hour.dir==null?"Windrichtung":null,hour.swell==null?"Wellenhöhe":null,hour.period==null?"Periode":null].filter(Boolean);
  return missingFields.length?`Teilweise verfügbar · fehlt: ${missingFields.join(", ")}`:"Vollständig verfügbar";
}
