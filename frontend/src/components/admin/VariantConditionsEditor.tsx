import { useMemo, useState } from "react";
import { Chip, Field, fieldClass } from "../ui";
import type { Suitability, VariantConditions } from "../../lib/api";
import {
  LEVELS,
  STYLES,
  FOIL_VARIANTS,
  levelLabel,
  parentSport,
  sportLabel,
  styleLabel,
  suitabilityLabel,
  variantLabel,
  variantsForSports,
} from "../../lib/labels";

/**
 * Per-variant suitability + conditions editor (Windfoil/Kitefoil). One card per
 * variant of the spot's selected wind-/kitesurf sports. Suitability defaults to
 * ``unbekannt`` (never a positive recommendation); the condition fields only
 * matter once a variant is marked geeignet/eingeschränkt. Shows, per card, what
 * is still missing for a belastbare Empfehlung and flags contradictions
 * (flat-water place vs. the depth a foil needs; competition level on an unproven
 * variant) — mirrors app.admin.constants.variant_consistency_warnings, but
 * inline for immediate feedback.
 */

type Conditions = Record<string, VariantConditions>;

const SUITABILITY_OPTIONS: Suitability[] = [
  "unbekannt",
  "geeignet",
  "eingeschraenkt",
  "ungeeignet",
];

function parseDirections(text: string): [number, number][] {
  const out: [number, number][] = [];
  for (const chunk of text.split(",")) {
    const m = chunk.trim().match(/^(\d{1,3})\s*[-–]\s*(\d{1,3})$/);
    if (!m) continue;
    const a = Number(m[1]);
    const b = Number(m[2]);
    if (a >= 0 && a <= 360 && b >= 0 && b <= 360) out.push([a, b]);
  }
  return out;
}

function directionsToText(windows?: [number, number][]): string {
  if (!windows?.length) return "";
  return windows.map(([a, b]) => `${a}-${b}`).join(", ");
}

export default function VariantConditionsEditor({
  sports,
  value,
  waterCharacter,
  onChange,
  onDirty,
}: {
  sports: string[];
  value: Conditions;
  waterCharacter: string[];
  onChange: (next: Conditions) => void;
  onDirty: () => void;
}) {
  const keys = useMemo(() => variantsForSports(sports), [sports]);
  // Local raw text for the direction inputs so partial typing ("200-") is fine;
  // parsed arrays are committed to `value` on every change.
  const [dirText, setDirText] = useState<Record<string, string>>(() =>
    Object.fromEntries(keys.map((k) => [k, directionsToText(value[k]?.wind_directions)])),
  );

  if (keys.length === 0) return null;

  const patch = (key: string, block: Partial<VariantConditions>) => {
    onDirty();
    const next: Conditions = { ...value, [key]: { ...(value[key] ?? {}), ...block } };
    onChange(next);
  };

  const setSuitability = (key: string, suitability: Suitability) =>
    patch(key, { suitability });

  const setText = (key: string, field: keyof VariantConditions, raw: string) =>
    patch(key, { [field]: raw.trim() ? raw : undefined } as Partial<VariantConditions>);

  const toggleChip = (
    key: string,
    field: "level" | "discipline",
    v: string,
  ) => {
    const current = value[key]?.[field] ?? [];
    const next = current.includes(v)
      ? current.filter((x) => x !== v)
      : [...current, v];
    patch(key, { [field]: next.length ? next : undefined } as Partial<VariantConditions>);
  };

  // Group variants under their parent sport so the card reads as a clear
  // second stage below the main-sport selection.
  const bySport = new Map<string, string[]>();
  for (const key of keys) {
    const sport = parentSport(key);
    bySport.set(sport, [...(bySport.get(sport) ?? []), key]);
  }

  return (
    <div className="space-y-6">
      <p className="-mt-1 text-caption text-muted">
        Eignung und Bedingungen je Variante. Fehlende Angaben bleiben „unbekannt"
        und erscheinen öffentlich nie als Empfehlung. Gemeinsame Ortsdaten (Untergrund,
        Wassertyp, Ausrichtung …) werden weiter oben nur einmal gepflegt.
      </p>
      {[...bySport.entries()].map(([sport, variantKeys]) => (
        <div key={sport} className="space-y-3">
          <h3 className="text-caption font-semibold uppercase tracking-wide text-muted">
            {sportLabel(sport)}
          </h3>
          {variantKeys.map((key) => {
            const block = value[key] ?? {};
            const suitability = block.suitability ?? "unbekannt";
            const offered = suitability === "geeignet" || suitability === "eingeschraenkt";
            const isFoil = (FOIL_VARIANTS as readonly string[]).includes(key);
            const shallow = waterCharacter.includes("flach");
            const depthSet = typeof block.usable_depth_m === "number";

            const missing: string[] = [];
            if (offered && !(block.wind_directions?.length)) missing.push("Windrichtung");
            if (offered && isFoil && !depthSet) missing.push("nutzbare Tiefe");

            const warnings: string[] = [];
            if (offered && isFoil && shallow && !depthSet)
              warnings.push(
                "Als nutzbar markiert, aber der Ort gilt als Flachwasser und es ist keine nutzbare Tiefe erfasst — Foils brauchen mehr Tiefe als ein flacher Einstieg bietet.",
              );
            if ((block.level ?? []).includes("competition") && suitability !== "geeignet")
              warnings.push(
                "Wettkampf-Level gesetzt, obwohl die Eignung nicht 'geeignet' ist — Wettkampf-/Weltklasse-Status nur für belegte Disziplinen vergeben.",
              );

            return (
              <div key={key} className="rounded-[14px] border border-line p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-label font-medium text-ink">{variantLabel(key)}</span>
                  <label className="flex items-center gap-2 text-caption text-muted">
                    Eignung
                    <select
                      className={fieldClass}
                      style={{ width: "auto" }}
                      value={suitability}
                      onChange={(e) => setSuitability(key, e.target.value as Suitability)}
                    >
                      {SUITABILITY_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {suitabilityLabel(s)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {isFoil && !offered && (
                  <p className="mt-2 text-caption text-muted">
                    Ohne belegte Eignung bleibt Windfoil/Kitefoil öffentlich „nicht
                    ausreichend bewertet".
                  </p>
                )}

                {offered && (
                  <div className="mt-3 grid gap-x-6 gap-y-4 sm:grid-cols-2">
                    <Field label="Windrichtungen" hint="Grad-Fenster, z. B. 200-260, 20-60">
                      <input
                        className={fieldClass}
                        value={dirText[key] ?? ""}
                        onChange={(e) => {
                          const raw = e.target.value;
                          setDirText((t) => ({ ...t, [key]: raw }));
                          const windows = parseDirections(raw);
                          patch(key, { wind_directions: windows.length ? windows : undefined });
                        }}
                        placeholder="200-260, 20-60"
                      />
                    </Field>
                    <Field
                      label={`Nutzbare Tiefe (m)${isFoil ? " – für Foil wichtig" : ""}`}
                    >
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        className={fieldClass}
                        value={typeof block.usable_depth_m === "number" ? block.usable_depth_m : ""}
                        onChange={(e) =>
                          patch(key, {
                            usable_depth_m: e.target.value === "" ? undefined : Number(e.target.value),
                          })
                        }
                      />
                    </Field>
                    <Field label="Gezeiten">
                      <input className={fieldClass} value={block.tide ?? ""}
                        onChange={(e) => setText(key, "tide", e.target.value)} />
                    </Field>
                    <Field label="Einstieg">
                      <input className={fieldClass} value={block.entry ?? ""}
                        onChange={(e) => setText(key, "entry", e.target.value)} />
                    </Field>
                    <Field label="Start-/Landefläche">
                      <input className={fieldClass} value={block.launch_area ?? ""}
                        onChange={(e) => setText(key, "launch_area", e.target.value)} />
                    </Field>
                    <Field label="Hindernisse">
                      <input className={fieldClass} value={block.hazards ?? ""}
                        onChange={(e) => setText(key, "hazards", e.target.value)} />
                    </Field>
                    <Field label="Lokale Regeln">
                      <input className={fieldClass} value={block.local_rules ?? ""}
                        onChange={(e) => setText(key, "local_rules", e.target.value)} />
                    </Field>
                    <Field label="Könnensniveau">
                      <div className="flex flex-wrap gap-1.5">
                        {LEVELS.map((l) => (
                          <Chip key={l} active={(block.level ?? []).includes(l)}
                            onClick={() => toggleChip(key, "level", l)}>
                            {levelLabel(l)}
                          </Chip>
                        ))}
                      </div>
                    </Field>
                    <Field label="Disziplin">
                      <div className="flex flex-wrap gap-1.5">
                        {STYLES.map((s) => (
                          <Chip key={s} active={(block.discipline ?? []).includes(s)}
                            onClick={() => toggleChip(key, "discipline", s)}>
                            {styleLabel(s)}
                          </Chip>
                        ))}
                      </div>
                    </Field>
                    <div className="sm:col-span-2">
                      <Field label="Redaktioneller Hinweis">
                        <textarea className={fieldClass} rows={2} value={block.notes ?? ""}
                          onChange={(e) => setText(key, "notes", e.target.value)} />
                      </Field>
                    </div>
                  </div>
                )}

                {offered && missing.length > 0 && (
                  <p className="mt-2 text-caption text-amber-700">
                    Für eine belastbare Empfehlung fehlt noch: {missing.join(", ")}.
                  </p>
                )}
                {warnings.map((w, i) => (
                  <p key={i} className="mt-2 text-caption text-amber-700">
                    ⚠ {w}
                  </p>
                ))}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
