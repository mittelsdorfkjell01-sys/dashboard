import type { ForecastSummaryRead, WeatherProvenance } from "./api";
import { bottomTypeLabel } from "./labels";
import type { Spot } from "./types";

export type SpotConditionHint = {
  id: "safety" | "forecast-wind" | "temperature" | "bottom";
  kind: "safety" | "wind" | "temperature" | "bottom";
  sentence: string;
  sourceLabel: "Redaktioneller Sicherheitshinweis" | "Vorhersage" | "Geprüftes Spotprofil";
  timing?: string;
  sourceUrl?: string;
};

const COMPASS_NAMES = [
  "Norden", "Nordnordosten", "Nordosten", "Ostnordosten",
  "Osten", "Ostsüdosten", "Südosten", "Südsüdosten",
  "Süden", "Südsüdwesten", "Südwesten", "Westsüdwesten",
  "Westen", "Westnordwesten", "Nordwesten", "Nordnordwesten",
] as const;

const finiteDirection = (value: number | null | undefined): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 && value < 360;

export function directionName(degrees: number): string {
  return COMPASS_NAMES[Math.round(degrees / 22.5) % 16];
}

function validDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed : null;
}

function instantLabel(value: string, timezone: string) {
  const date = validDate(value);
  if (!date) return null;
  try {
    return new Intl.DateTimeFormat("de-DE", {
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: timezone,
      timeZoneName: "short",
    }).format(date);
  } catch {
    return null;
  }
}

function provenanceTiming(provenance: WeatherProvenance | null | undefined) {
  if (!provenance?.valid_at || !provenance.captured_at) return null;
  const valid = instantLabel(provenance.valid_at, provenance.spot_timezone);
  const captured = instantLabel(provenance.captured_at, provenance.spot_timezone);
  return valid && captured ? `Gültig: ${valid} · Datenstand: ${captured}` : null;
}

function usableForecast(provenance: WeatherProvenance | null | undefined) {
  return Boolean(
    provenance &&
      provenance.source_type === "forecast" &&
      provenance.observation_type === "forecast" &&
      provenance.stale === false &&
      provenance.availability === "available" &&
      provenance.valid_at &&
      provenance.captured_at,
  );
}

function temperatureSentence(air: number | null, water: number | null) {
  if (air != null && water != null) {
    return `Voraussichtlich ${Math.round(air)} °C Lufttemperatur und ${Math.round(water)} °C Wassertemperatur.`;
  }
  if (air != null) return `Voraussichtlich ${Math.round(air)} °C Lufttemperatur.`;
  if (water != null) return `Voraussichtlich ${Math.round(water)} °C Wassertemperatur.`;
  return null;
}

function bottomSentence(values: string[]) {
  if (values.length === 1 && values[0] === "rock") {
    return "Laut Spotprofil felsiger Untergrund.";
  }
  if (values.length === 1 && values[0] === "reef") {
    return "Laut Spotprofil Untergrund aus Riff.";
  }
  const labels = values.map(bottomTypeLabel).filter(Boolean);
  return labels.length ? `Laut Spotprofil Untergrund: ${labels.join(" und ")}.` : null;
}

/** Build factual, independently sourced hints. Missing, stale or unreviewed
 * inputs disappear; the editorial ``facingDeg`` value is intentionally never
 * consulted for coastal classification. */
export function buildSpotConditionHints(
  spot: Spot,
  forecast: ForecastSummaryRead | null | undefined,
): SpotConditionHint[] {
  const hints: SpotConditionHint[] = [];
  if (spot.safetyNotice?.trim()) {
    const source = spot.contentSources?.find(
      (item) => item.field_path === "editorial.safety_notice" && item.verification_status === "verified",
    );
    hints.push({
      id: "safety",
      kind: "safety",
      sentence: spot.safetyNotice.trim(),
      sourceLabel: "Redaktioneller Sicherheitshinweis",
      ...(source ? {
        timing: `Quelle geprüft: ${formatCheckedDate(source.checked_at)}`,
        sourceUrl: source.url,
      } : {}),
    });
  }
  const hour = forecast?.hour;
  const provenance = hour?.provenance;
  const normal = hour?.coastal_normal_deg;
  const reviewed = validDate(hour?.coastal_profile_reviewed_at);
  const profileSuitable =
    reviewed != null &&
    finiteDirection(normal) &&
    ["coastal", "extended", "advanced"].includes(hour?.quality_tier ?? "");
  const dynamicUsable = hour?.stale !== true && usableForecast(provenance);
  const direction = hour?.dir;

  if (
    dynamicUsable &&
    profileSuitable &&
    finiteDirection(direction) &&
    hour?.coastal_classification === "offshore"
  ) {
    hints.push({
      id: "forecast-wind",
      kind: "wind",
      sentence: `Voraussichtlich ablandiger Wind – der Wind kommt aus ${directionName(direction)}.`,
      sourceLabel: "Vorhersage",
      timing: provenanceTiming(provenance) ?? undefined,
    });
  }

  const air = dynamicUsable && Number.isFinite(hour?.air) ? hour!.air : null;
  const water = dynamicUsable && Number.isFinite(hour?.sst) ? hour!.sst : null;
  const sentence = temperatureSentence(air, water);
  const timing = provenanceTiming(provenance);
  if (sentence && timing) {
    hints.push({ id: "temperature", kind: "temperature", sentence, sourceLabel: "Vorhersage", timing });
  }

  const bottom = bottomSentence(spot.bottomType ?? []);
  if (bottom) {
    hints.push({ id: "bottom", kind: "bottom", sentence: bottom, sourceLabel: "Geprüftes Spotprofil" });
  }
  return hints;
}

function formatCheckedDate(value: string): string {
  const parsed = validDate(value);
  return parsed
    ? new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(parsed)
    : "Datum unbekannt";
}
