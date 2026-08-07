// Shared view-model types + small pure helpers. These used to live in
// src/data/*.ts alongside mock data; the mock data is gone (all pages read the
// API now), the types stay.

import type { FacilityMap } from "./api";
import type { CreditSource } from "./imageCredit";

// --- spot / region view models ---------------------------------------------

export type TagKind = "wave" | "level" | "water";
export interface Tag {
  label: string;
  kind: TagKind;
}

export interface Spot {
  id: string;
  name: string;
  region: string;
  wind: number; // kts (typical / current)
  favorite?: boolean;
  tags: Tag[];
  image: string; // "" = no image → branded fallback
  hero?: string;
  heroFocal?: { x: number; y: number } | null; // object-position % for the crop
  // Full attribution (photographer, provider, licence + their links). One
  // object rather than loose strings, so stock, Commons and community photos
  // all render through the same credit line.
  heroCredit?: CreditSource | null;
  heroDelivery?: "hotlinked" | "hosted"; // hotlinked images resize via the provider CDN
  coords?: [number, number]; // [lat, lng]
  windDir?: number; // degrees the wind comes FROM
  waveDir?: number;
  coast?: number;

  // populated from the backend
  uuid?: string;
  slug?: string;
  regionId?: string;
  sports?: string[];
  description?: string;
  level?: string[];
  waterTypes?: string[];
  bottomType?: string[];
  waterCharacter?: string[];
  style?: string[];
  facilities?: FacilityMap | null;
  /** Derived 52-week climatology (from the detail record); null when not derived. */
  climatology?: Record<string, any> | null;
  /** Admin-set preview frame for the wind/wave flow map (editorial.map_view). */
  mapView?: { center: [number, number]; zoom: number } | null;
}

export interface RegionInfo {
  slug: string;
  name: string;
  country: string;
  spots: Spot[];
  center: [number, number];
}

// --- spot-detail panel types ------------------------------------------------

export type FacilityKind = "parking" | "school" | "shower" | "food" | "camping";
export interface Facility {
  kind: FacilityKind;
  title: string;
  note: string;
  /** true = vorhanden, false = demonstrably nicht vorhanden (shown struck
   *  through/muted), null = unbekannt (no entry — shown dimmed, never as
   *  "not present"). */
  available: boolean | null;
}

export interface Tip {
  author: string;
  text: string;
}

/** One 3-hour block of the forecast's always-visible weekly overview
 *  (Ebene 1) — the block's *best* hour (highest average wind). */
export interface DayBlock {
  label: string; // "06–09" etc.
  wind: number | null; // kts, that hour's average wind
  dir: number | null; // that hour's wind direction
}

/** One day of the weekly overview: 5 blocks (06–21h) + the day's headline
 *  direction/max, both derived from those same blocks. */
export interface DayBlocks {
  day: string; // MON…SUN
  date: string; // short display date, e.g. "23.07."
  blocks: DayBlock[];
  windDir: number | null; // midday direction, for the single day-column arrow
  maxWind: number | null; // kts, the day's peak block value
}

/** One 2-hour block of a day's collapsible detail graph (Ebene 2). */
export interface DetailBlock {
  label: string; // "06–08" etc.
  windAvg: number | null; // kts, mean wind across the window (not max)
  gustMax: number | null; // kts, peak gust across the window
  dir: number | null; // representative wind direction for this block's arrow
}

/** One day's detail graph: 8 blocks (06–22h) plus the day-level readings
 *  shown as a compact number row above the chart (never plotted). */
export interface DayDetail {
  day: string;
  date: string;
  blocks: DetailBlock[];
  waveHeight: number | null; // m
  wavePeriod: number | null; // s
  airTemp: number | null; // °C
}

/** One raw hour of the Stundentabelle (Daten tab) — every variable the table
 *  has a row for, unaggregated (unlike `DetailBlock`, which is a 2h mean). */
export interface HourRow {
  time: string; // "HH:MM", local (see hourOf/seasonView for why not a Date)
  hour: number; // 0–23, for night-tint / mobile 3h-sampling logic
  wind: number | null; // kts
  gust: number | null; // kts
  dir: number | null; // degrees
  waveHeight: number | null; // m
  swellDir: number | null; // degrees
  period: number | null; // s
  air: number | null; // °C
  water: number | null; // °C (sst)
  precip: number | null; // mm
}

/** One day of the Stundentabelle: every hour the forecast actually reports,
 *  in order — a short/incomplete day (fewer than 24 hours) is valid, not an
 *  error, since the horizon's last day is often partial. */
export interface DayHours {
  day: string;
  date: string; // short display date, e.g. "23.07."
  isoDate: string; // "YYYY-MM-DD", for sunTimes() — display date has no year
  hours: HourRow[];
}

/** A month's mean wind, one value per week. */
export interface MonthWind {
  month: string; // JAN…DEZ
  weeks: number[];
}

export interface SpotFact {
  label: string;
  value: string;
}

/** Water character — drives the wave animation on the spot map. */
export type WaterType = "flat" | "chop" | "swell";

/** One month of the region-season chart. */
export interface RegionMonth {
  month: string;
  working: number;
  total: number;
  wind: number;
}

// --- helpers ---------------------------------------------------------------

const slugify = (s: string) =>
  s
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

/** Slug for the region a spot belongs to, e.g. "Sardinien, Italien" → "sardinien". */
export const regionSlug = (region: string) => slugify(region.split(",")[0]);
