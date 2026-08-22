import { expect, test } from "@playwright/test";

const weeks=Array.from({length:52},(_,i)=>({week:i+1,sample_years:20,successful_years:i%3===0?0:12,reliability_percent:i%3===0?0:60,median_usable_days:2,median_session_hours:6,p25_session_hours:3,p75_session_hours:9,quality_status:"high"}));
const status={state:"complete",stale:false,latest:{id:"run-1",status:"ready",period:[2006,2025],algorithm_version:"wind-climatology-v3.0",config_hash:"hash",started_at:"2026-08-22T10:00:00Z",completed_at:"2026-08-22T10:04:00Z",activated_at:"2026-08-22T10:04:00Z",is_active:true,quality:{valid_years:20,quality_status:"high"},warnings:[],error_category:null,error:null},active:null as unknown, directions:{reviewed:true,windows:[{start_deg:337.5,end_deg:0},{start_deg:0,end_deg:22.5}],usable_available:true},cell:{mode:"automatic",spot:[54.4,10.2],requested:[54.4,10.2],actual:[54.5,10.25],distance_km:11.2,model:"ERA5",resolution_degrees:.25,status:"ready",warnings:[]},public_effect:"none"};
status.active=status.latest;

test.beforeEach(async({page})=>{
  await page.route("**/auth/me",r=>r.fulfill({json:{id:"admin-1",email:"admin@example.com",display_name:"Admin",role:"admin"}}));
  await page.route("**/admin/notifications/unread-count",r=>r.fulfill({json:{count:0}}));
  await page.route("**/admin/environment",r=>r.fulfill({json:{app_env:"test",database_target:"local",admin_writes_blocked:false,allow_remote_writes:false}}));
  await page.route("**/admin/weather/spots/spot-1/wind-climatology-v3/status",r=>r.fulfill({json:status}));
  await page.route("**/admin/weather/spots/spot-1/wind-climatology-v3/directions",r=>r.fulfill({json:r.request().method()==="PUT"?{sectors:[0,3,15],reviewed:true,reviewed_at:"2026-08-22T12:00:00Z",updated_at:"2026-08-22T12:00:00Z",run:{id:"run-2",status:"pending",created:true}}:{sectors:[0,15],reviewed:true,reviewed_at:"2026-08-22T10:00:00Z",updated_at:"2026-08-22T10:00:00Z"}}));
  await page.route("**/admin/weather/spots/spot-1/wind-climatology-v3/cell",r=>r.fulfill({json:{cell:status.cell,run:{id:"run-2",status:"pending",created:true}}}));
  await page.route("**/admin/weather/spots/spot-1/wind-climatology-v3/runs",r=>r.fulfill({status:202,json:{run_id:"run-2",status:"pending",created:true}}));
  await page.route("**/admin/weather/spots/spot-1/wind-climatology-v3/variant?**",r=>{const url=new URL(r.request().url());const mode=url.searchParams.get("direction_mode")??"all";r.fulfill({json:{run_id:"run-1",period:[2006,2025],algorithm_version:"wind-climatology-v3.0",variant:{min_wind_kn:Number(url.searchParams.get("min_wind_kn")),max_wind_kn:Number(url.searchParams.get("max_wind_kn")),direction_mode:mode,weeks:mode==="usable"?weeks.map(w=>({...w,reliability_percent:(w.reliability_percent??0)/2,median_session_hours:3})):weeks}}})});
});

test("administrator verwaltet V3 ohne Providerabruf",async({page},testInfo)=>{
  await page.goto("/admin/spot/spot-1/wind-climatology-v3");
  await expect(page.getByRole("heading",{name:"Windklimatologie V3"})).toBeVisible();
  await expect(page.getByRole("button",{name:/Wind aus/})).toHaveCount(16);
  await page.getByRole("button",{name:/ONO, Wind aus/}).click();
  await page.getByRole("button",{name:"Richtungen speichern"}).click();
  await expect(page.getByText(/V3-Lauf eingeplant/)).toBeVisible();
  await page.getByRole("button",{name:"Manuell"}).click();
  await page.getByLabel("Latitude").fill("54.45"); await page.getByLabel("Longitude").fill("10.3");
  await page.getByRole("button",{name:"Raster speichern"}).click();
  await page.getByRole("button",{name:"20–30"}).click();
  await page.getByRole("button",{name:"Passende Richtungen"}).click();
  await expect(page.getByRole("img",{name:/Saisonwoche/})).toHaveCount(52);
  if(process.env.CAPTURE_V3_REVIEW) await page.screenshot({path:`../.impeccable/review/${testInfo.project.name.includes("mobile")?"mobile":"desktop"}.png`,fullPage:true});
  page.once("dialog",d=>d.accept()); await page.getByRole("button",{name:"V3 neu berechnen"}).click();
  await expect(page.getByText("V3-Lauf wurde eingeplant.")).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});

test("Betriebsansicht trennt V3 und Legacy eindeutig",async({page},testInfo)=>{
  await page.route("**/admin/weather/wind-climatology-v3/operations",r=>r.fulfill({json:{counts:{current:18,stale:3,missing:20,failed:2,inflight:4},queue_depth:2,recent_runs:[{run_id:"run-1",spot_id:"spot-1",spot_name:"Ein außergewöhnlich langer Spotname an der Nordseeküste",status:"failed",period:[2006,2025],algorithm_version:"wind-climatology-v3.0",quality_status:"limited",created_at:"2026-08-22T10:00:00Z",started_at:"2026-08-22T10:01:00Z",completed_at:"2026-08-22T10:04:00Z",duration_s:180,error_category:"provider",has_active_version:true}]}}));
  await page.route("**/admin/operations",r=>r.request().resourceType()==="document"?r.continue():r.fulfill({json:{freshness:{missing:4,stale:1,current:40,failed:1},queue_depth:0,job_status:{},recent_jobs:[],public_update:{climatology_cron:"halbjährlich",edge_cache:"Legacy-Cache"}}}));
  await page.goto("/admin/operations");
  await expect(page.getByRole("heading",{name:"Windklimatologie V3"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Legacy V1/V2"})).toBeVisible();
  await expect(page.getByText("Ein außergewöhnlich langer Spotname an der Nordseeküste")).toBeVisible();
  if(process.env.CAPTURE_V3_REVIEW) await page.screenshot({path:`../.impeccable/review/operations-${testInfo.project.name.includes("mobile")?"mobile":"desktop"}.png`,fullPage:true});
});
