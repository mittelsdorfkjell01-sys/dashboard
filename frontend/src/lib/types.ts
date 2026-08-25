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
  wind: number; // kts, typical/editorial value — never a live reading (see adapt.ts)
  favorite?: boolean;
  tags: Tag[];
  image: string; // "" = no image → branded fallback
  hero?: string;
  heroFocal?: { x: number; y: number } | null; // object-position % for the crop
  heroFocalMobile?: { x: number; y: number } | null; // mobile override, optional
  heroRotation?: number; // subtle horizon correction in degrees
  heroReel?: boolean; // in the curated landing-hero rotation (admin Hero tab)
  // Full attribution (photographer, provider, licence + their links). One
  // object rather than loose strings, so stock, Commons and community photos
  // all render through the same credit line.
  heroCredit?: CreditSource | null;
  heroDelivery?: "hotlinked" | "hosted"; // hotlinked images resize via the provider CDN
  coords?: [number, number]; // [lat, lng]
  /** Redaktioneller Orientierungswert; niemals aktuelle Wetterrichtung oder Küstennormale. */
  facingDeg?: number;

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
  /** Admin-set preview frame for the wind/wave map (editorial.map_view). */
  mapView?: { center: [number, number]; zoom: number } | null;

  // --- tile-facing fields (SpotCard) ---------------------------------------
  /** Bare region name, separate from the combined `region` label (tile joins
   *  it with the country itself, e.g. "Tarifa · Spanien"). */
  regionName?: string;
  /** ISO country code (e.g. "PT") — resolved to a display name via lib/flags. */
  regionCountry?: string | null;
  /** Typical wind, kts — exactly one of typicalWindKt/typicalWaveHeightM is
   *  set, gated by the spot's primary sport (see app.scoring.context on the
   *  backend). Distinct from `wind` above, which non-tile consumers rely on
   *  as a plain always-kts fallback. */
  typicalWindKt?: number | null;
  /** Typical wave height, m — set for surf spots instead of typicalWindKt. */
  typicalWaveHeightM?: number | null;
  /** Weighted monthly daylight availability for 15–20 kt from active V2. */
  windAvailability?: number[] | null;
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
