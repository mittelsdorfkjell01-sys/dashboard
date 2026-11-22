/** Every area of a spot page a visitor can flag a correction for, in the order
 *  the page reads. The keys are a contract: the backend accepts exactly these
 *  (`SPOT_EDIT_FIELDS` in `app/community/service.py`) and the admin review queue files by them, so
 *  a new area needs both sides. The labels use the page's own words — "Level",
 *  "Gewässer", "Untergrund" are what the visitor just read — so nobody has to
 *  guess which bucket a wrong value belongs in. */
export const SPOT_EDIT_TARGETS: { key: string; label: string }[] = [
  { key: "name", label: "Name des Spots" },
  { key: "region", label: "Region / Land" },
  { key: "sports", label: "Sportarten" },
  { key: "description", label: "Beschreibung" },
  { key: "hazards", label: "Sicherheit und Gefahren" },
  { key: "data", label: "Spotprofil (Level, Gewässer, Untergrund, Windrichtung)" },
  { key: "facilities", label: "Ausstattung" },
  { key: "location", label: "Lage auf der Karte" },
  { key: "photos", label: "Fotos" },
  { key: "other", label: "Sonstiges" },
];

export function spotEditTargetLabel(key: unknown): string {
  return SPOT_EDIT_TARGETS.find((t) => t.key === key)?.label ?? "Sonstiges";
}
