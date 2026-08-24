import type { MeteogramModel } from "./meteogramModel";

export type MeteogramViewMode = "24h" | "48h" | "5d";

export function initialMeteogramView(): MeteogramViewMode {
  return typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches ? "24h" : "5d";
}

export function closestDetailDayIndex(model: MeteogramModel, now = Date.now()): number {
  if (!model.detailDays.length) return 0;
  const closest = model.slots.reduce((best, slot) => Math.abs(Date.parse(slot.utcKey) - now) < Math.abs(Date.parse(best.utcKey) - now) ? slot : best, model.slots[0]);
  return Math.max(0, model.detailDays.findIndex((day) => (day.local_date ?? day.date) === closest.localDate));
}

export function projectMeteogramView(model: MeteogramModel, dayIndex: number, mode: MeteogramViewMode): MeteogramModel {
  if (mode === "5d" || !model.slots.length) return model;
  const day = model.detailDays[Math.min(Math.max(dayIndex, 0), model.detailDays.length - 1)];
  const first = day?.hours[0];
  if (!first) return { ...model, slots: [], dayGroups: [], temperatureSegments: [] };
  const start = Date.parse(first.utcKey);
  const end = start + (mode === "24h" ? 24 : 48) * 3_600_000;
  const slots = model.slots.filter((slot) => { const epoch=Date.parse(slot.utcKey); return epoch >= start && epoch < end; });
  const dayGroups: MeteogramModel["dayGroups"] = [];
  slots.forEach((slot,index)=>{const current=dayGroups[dayGroups.length-1];if(current?.date===slot.localDate)current.count+=1;else {const source=model.dayGroups.find((group)=>group.date===slot.localDate);dayGroups.push({date:slot.localDate,start:index,count:1,confidence:source?.confidence??null,confidenceSource:source?.confidenceSource??null});}});
  const keys=new Set(slots.map((slot)=>slot.utcKey));
  const temperatureSegments=model.temperatureSegments.map((segment)=>segment.filter((slot)=>keys.has(slot.utcKey))).filter((segment)=>segment.length);
  return { ...model, slots, dayGroups, temperatureSegments };
}

export function closestSlotOnDay(model:MeteogramModel, dayIndex:number, selectedAtUtc:string|null) {
  const targetHours=model.detailDays[Math.min(Math.max(dayIndex,0),model.detailDays.length-1)]?.hours??[];
  if(!targetHours.length)return null;
  const selected=model.slots.find((slot)=>slot.utcKey===selectedAtUtc);
  if(!selected)return targetHours[0].utcKey;
  // Map by ordinal position within the day (n-th hour -> n-th hour) rather than
  // nearest local clock time: this stays correct across DST-shifted day lengths
  // without any local-time arithmetic, and degrades gracefully by clamping when
  // the target day has fewer hours than the source day.
  const sourceHours=model.detailDays.find((day)=>(day.local_date??day.date)===selected.localDate)?.hours??[];
  const sourcePosition=sourceHours.findIndex((hour)=>hour.utcKey===selected.utcKey);
  if(sourcePosition<0)return targetHours[0].utcKey;
  return targetHours[Math.min(sourcePosition,targetHours.length-1)].utcKey;
}
