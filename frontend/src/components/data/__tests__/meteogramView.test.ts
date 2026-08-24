import { describe, expect, it } from "vitest";
import type { ForecastDay, ForecastHour, ForecastSeries } from "../../../lib/api";
import { normalizeForecast } from "../../../lib/forecastNormalization";
import { buildMeteogramModel } from "../meteogramModel";
import { closestSlotOnDay, projectMeteogramView } from "../meteogramView";

const hour=(time:string):ForecastHour=>({time,wind:10,gust:14,dir:180,air:15,swell:null,period:null,swell_dir:null,precip:0,sst:null});
const days:ForecastDay[]=Array.from({length:5},(_,day)=>({date:`2026-08-${String(23+day).padStart(2,"0")}`,local_date:`2026-08-${String(23+day).padStart(2,"0")}`,detail:"hourly",confidence:"hoch",hours:Array.from({length:8},(_,slot)=>hour(`2026-08-${String(23+day).padStart(2,"0")}T${String(slot*3).padStart(2,"0")}:00:00Z`)),summary:{wind_avg:10,wind_max:10,gust_max:14,air_min:15,air_max:15,swell_max:null}}));
const source:ForecastSeries={spot_id:"spot",model:"test",generated_at:"2026-08-23T00:00:00Z",timezone:"UTC",availability:{atmosphere:"available",solar:"available",marine:"not_applicable_inland"},days};

describe("meteogram responsive projection",()=>{
  it("projects 24 and 48 hours without changing scales or values",()=>{
    const full=buildMeteogramModel(normalizeForecast(source));
    const one=projectMeteogramView(full,1,"24h"),two=projectMeteogramView(full,1,"48h"),five=projectMeteogramView(full,1,"5d");
    expect(one.slots).toHaveLength(8);
    expect(two.slots).toHaveLength(16);
    expect(five.slots).toHaveLength(40);
    expect(one.scales).toBe(full.scales);
    expect(two.scales).toBe(full.scales);
    expect(one.slots[0]).toBe(full.detailDays[1].hours[0]);
  });

  it("uses actual UTC duration across a local DST day and never synthesizes slots",()=>{
    const full=buildMeteogramModel(normalizeForecast(source));
    expect(projectMeteogramView(full,4,"48h").slots).toHaveLength(8);
  });

  it("moves a day selection to the same ordinal hour-of-day with a unique UTC key",()=>{
    const full=buildMeteogramModel(normalizeForecast(source));
    const selected=full.detailDays[0].hours[3];
    expect(closestSlotOnDay(full,1,selected.utcKey)).toBe(full.detailDays[1].hours[3].utcKey);
    expect(closestSlotOnDay(full,1,"not-a-time")).toBe(full.detailDays[1].hours[0].utcKey);
  });

  it("clamps to the last hour when the target day has fewer hours than the source day",()=>{
    const shortDays:ForecastDay[]=[
      days[0],
      {...days[1],hours:days[1].hours.slice(0,3)},
    ];
    const full=buildMeteogramModel(normalizeForecast({...source,days:shortDays}));
    const selected=full.detailDays[0].hours[6];
    expect(closestSlotOnDay(full,1,selected.utcKey)).toBe(full.detailDays[1].hours[2].utcKey);
  });
});
