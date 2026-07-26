// Single source of truth for translating backend enum keys → German display
// labels. The keys mirror app/admin/constants.py (LEVELS, WATER_CHARACTERS,
// STYLES, FACILITY_KINDS); keep them in sync with the backend.

import type { FacilityKind } from "./api";

export const LEVELS = ["beginner", "intermediate", "advanced", "pro"] as const;
export const WATER_CHARACTERS = [
  "flach",
  "chop",
  "welle_klein",
  "welle_gross",
  "tiefes_wasser",
] as const;
export const STYLES = ["freeride", "freestyle", "big_air", "wave_riding"] as const;
export const FACILITY_KINDS: FacilityKind[] = [
  "parking",
  "shower",
  "food",
  "camping",
  "school",
];

export const LEVEL_LABELS: Record<string, string> = {
  beginner: "Anfänger",
  intermediate: "Fortgeschritten",
  advanced: "Könner",
  pro: "Profi",
};

export const WATER_CHARACTER_LABELS: Record<string, string> = {
  flach: "Flachwasser",
  chop: "Chop / Kabbelwelle",
  welle_klein: "Kleine Welle",
  welle_gross: "Große Welle",
  tiefes_wasser: "Tiefes Wasser",
};

export const STYLE_LABELS: Record<string, string> = {
  freeride: "Freeride",
  freestyle: "Freestyle",
  big_air: "Big Air",
  wave_riding: "Wellenreiten",
};

export const FACILITY_LABELS: Record<FacilityKind, string> = {
  parking: "Parkplatz",
  shower: "Dusche",
  food: "Gastronomie",
  camping: "Camping",
  school: "Surfschule / Verleih",
};

export const SPORT_LABELS: Record<string, string> = {
  kitesurf: "Kitesurfen",
  wavekite: "Wavekiten",
  windsurf: "Windsurfen",
  wing: "Wingfoilen",
  surf: "Surfen",
};

// Admin roles (Sprint A). Keys stay 'admin'/'curator' in the backend; these are
// just the German display labels ("Moderator" is the operator-facing term).
export const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  curator: "Moderator",
};
export const roleLabel = (k?: string | null) => (k ? ROLE_LABELS[k] ?? k : "");

// Spot lifecycle status (Sprint B admin).
export const STATUS_LABELS: Record<string, string> = {
  draft: "Entwurf",
  published: "Veröffentlicht",
  archived: "Archiviert",
};
export const statusLabel = (k?: string | null) =>
  k ? STATUS_LABELS[k] ?? k : "";

// Readiness gap field keys → short German hints (Sprint B). Falls back to the
// raw key so an unmapped field is still legible.
export const GAP_LABELS: Record<string, string> = {
  water_type: "Gewässerart",
  bottom_type: "Untergrund",
  level: "Level",
  water_character: "Wasserart",
  "editorial.description": "Beschreibung",
  "editorial.usable_wind_directions": "Nutzbare Windrichtungen",
  "editorial.tide": "Gezeiten",
  climatology: "Klimatologie",
  image: "Titelbild",
};
export const gapLabel = (k: string) => GAP_LABELS[k] ?? k;

// Audit action keys (spot_audit.action) → German verbs for the dashboard preview.
export const ACTION_LABELS: Record<string, string> = {
  create: "Angelegt",
  update: "Bearbeitet",
  publish: "Veröffentlicht",
  unpublish: "Offline genommen",
  archive: "Archiviert",
  image: "Bild geändert",
  override: "Wert überschrieben",
  revert: "Override entfernt",
};
export const actionLabel = (k?: string | null) =>
  k ? ACTION_LABELS[k] ?? k : "";

// Weather model choices for a region/spot (model_pref). Empty = auto-select by
// coordinates. Values are valid Open-Meteo ids (mirror app/live/models.py); the
// backend normalises "icon" → "icon_seamless". Each carries a short "when to use"
// hint shown in the help tooltip.
export interface ModelOption {
  value: string;
  label: string;
  hint: string;
}
export const MODEL_PREF_OPTIONS: ModelOption[] = [
  {
    value: "",
    label: "Automatisch (nach Koordinaten)",
    hint: "Das System wählt selbst das beste regionale Modell für die Position. Empfohlen im Zweifel.",
  },
  {
    value: "icon",
    label: "DWD ICON — automatisch D2/EU/global",
    hint: "DWD-Modellfamilie, die je nach Ort automatisch die beste ICON-Domain wählt. Gute Allround-Wahl in Europa.",
  },
  {
    value: "icon_d2",
    label: "DWD ICON-D2 — Mitteleuropa, ~2 km",
    hint: "Höchste Auflösung für DE/AT/CH/BeNeLux/Alpen. Beste Wahl für Küsten- und Lokaldetails in Mitteleuropa.",
  },
  {
    value: "icon_eu",
    label: "DWD ICON-EU — Europa, ~7 km",
    hint: "Ganz Europa in ~7 km. Nutzen, wenn der Spot außerhalb der ICON-D2-Domäne liegt.",
  },
  {
    value: "meteofrance_arome_france_hd",
    label: "Météo-France AROME — Frankreich, ~1,3 km",
    hint: "Feinste Auflösung für Frankreich und seine Küsten. Beste Wahl für französische Spots.",
  },
  {
    value: "gfs_seamless",
    label: "NOAA GFS — global",
    hint: "Globales US-Modell. Für Spots außerhalb Europas oder als unabhängiger Vergleich.",
  },
  {
    value: "ecmwf_ifs025",
    label: "ECMWF IFS — global, ~25 km",
    hint: "Globales ECMWF-Modell, oft sehr gute Qualität. Weltweit einsetzbar, gröber als die regionalen Modelle.",
  },
  {
    value: "best_match",
    label: "Open-Meteo Best-Match — Blend (Fallback)",
    hint: "Open-Meteos automatischer Blend über mehrere Modelle. Robuster Fallback überall.",
  },
];
export const modelPrefLabel = (v?: string | null) =>
  MODEL_PREF_OPTIONS.find((o) => o.value === (v ?? ""))?.label ?? v ?? "";

export const levelLabel = (k?: string | null) => (k ? LEVEL_LABELS[k] ?? k : "");
export const waterCharacterLabel = (k?: string | null) =>
  k ? WATER_CHARACTER_LABELS[k] ?? k : "";
export const styleLabel = (k: string) => STYLE_LABELS[k] ?? k;
export const facilityLabel = (k: FacilityKind) => FACILITY_LABELS[k] ?? k;
export const sportLabel = (k: string) => SPORT_LABELS[k] ?? k;

export const styleList = (styles?: string[] | null) =>
  (styles ?? []).map(styleLabel).join(", ");
