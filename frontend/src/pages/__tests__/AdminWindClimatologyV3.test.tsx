import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { DirectionCompass, WeekChart } from "../AdminWindClimatologyV3";
import type { V3Variant, V3Week } from "../../lib/api";

const week=(index:number):V3Week=>({week:index+1,reliability_percent:index===0?0:50,sample_years:20,successful_years:10,median_usable_days:2,median_session_hours:6,p25_session_hours:3,p75_session_hours:9,quality_status:"high"});
const data:V3Variant={run_id:"run",period:[2006,2025],algorithm_version:"v3",variant:{min_wind_kn:15,max_wind_kn:20,direction_mode:"all",weeks:Array.from({length:52},(_,i)=>week(i))}};

describe("Windklimatologie V3 Admin",()=>{
  it("renders all 16 keyboard buttons and separated selections",()=>{
    const html=renderToStaticMarkup(<DirectionCompass selected={[0,3,15]} onChange={()=>undefined}/>);
    expect((html.match(/aria-pressed=/g)??[]).length).toBe(16);
    expect(html).toContain("N, Wind aus 0 bis 22.5 Grad, ausgewählt");
    expect(html).toContain("NNW, Wind aus 337.5 bis 0 Grad, ausgewählt");
    expect(html).toContain("N, ONO, NNW");
  });
  it("renders exactly 52 unchanged bars and keeps zero at zero",()=>{
    const html=renderToStaticMarkup(<WeekChart data={data} min={15} max={20} mode="all"/>);
    expect((html.match(/role="img"/g)??[]).length).toBe(52);
    expect(html).toContain("Saisonwoche 1: 0 Prozent");
    expect(html).toContain("height:0%");
    expect(html).toContain("P25–P75: 3–9");
  });
  it("rejects any artifact that does not contain exactly 52 weeks",()=>{
    const broken={...data,variant:{...data.variant,weeks:data.variant.weeks.slice(0,51)}};
    expect(renderToStaticMarkup(<WeekChart data={broken} min={15} max={20} mode="all"/>)).toContain("Erwartet wurden 52 Wochen");
  });
});
