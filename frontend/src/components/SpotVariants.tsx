import type { Spot } from "../lib/types";
import type { Suitability, VariantConditions } from "../lib/api";
import {
  FOIL_VARIANTS,
  SPORT_VARIANTS,
  sportLabel,
  suitabilityLabel,
  variantLabel,
} from "../lib/labels";
import { levelLabel, styleLabel } from "../lib/labels";

/**
 * Per-variant suitability + key conditions for a spot's wind-/kitesurf
 * disciplines (Finne/Windfoil, klassisch/Kitefoil). Each variant carries its
 * *own* status — `unbekannt` renders neutral and is never a positive
 * recommendation, `ungeeignet` is muted, and a foil variant with no proven
 * parameters is labelled "nicht ausreichend bewertet" rather than shown green.
 * Common place data lives elsewhere on the page; only variant-specific values
 * appear here.
 */

const TONE: Record<Suitability, string> = {
  geeignet: "border-teal/40 bg-teal/10 text-teal",
  eingeschraenkt: "border-amber-500/40 bg-amber-500/10 text-amber-700",
  ungeeignet: "border-line bg-band text-muted line-through",
  unbekannt: "border-line bg-band/60 text-muted",
};

function directionsText(windows?: [number, number][]): string | null {
  if (!windows || windows.length === 0) return null;
  return windows.map(([a, b]) => `${Math.round(a)}–${Math.round(b)}°`).join(", ");
}

function ConditionRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 text-caption">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="text-ink">{value}</span>
    </div>
  );
}

function VariantCard({
  variantKey,
  block,
}: {
  variantKey: string;
  block: VariantConditions | undefined;
}) {
  const suitability = block?.suitability ?? "unbekannt";
  const offered = suitability === "geeignet" || suitability === "eingeschraenkt";
  const isFoil = (FOIL_VARIANTS as readonly string[]).includes(variantKey);
  const directions = directionsText(block?.wind_directions);
  const depth =
    block?.usable_depth_m != null && block.usable_depth_m !== "n/a"
      ? `${block.usable_depth_m} m`
      : null;

  return (
    <div className="rounded-[14px] border border-line p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-label font-medium text-ink">{variantLabel(variantKey)}</span>
        <span className={`rounded-full border px-2 py-0.5 text-caption font-medium ${TONE[suitability]}`}>
          {suitabilityLabel(suitability)}
        </span>
      </div>

      {/* A foil variant that isn't proven usable is honestly labelled — never a
          green forecast off invented thresholds. */}
      {isFoil && !offered && (
        <p className="mt-2 text-caption text-muted">
          Nicht ausreichend bewertet — Foil-Bedingungen für diesen Spot sind noch
          nicht belegt.
        </p>
      )}

      {offered && (
        <div className="mt-2 space-y-1">
          {directions && <ConditionRow label="Windrichtung" value={directions} />}
          {depth && <ConditionRow label="Nutzbare Tiefe" value={depth} />}
          {block?.tide && <ConditionRow label="Gezeiten" value={block.tide} />}
          {block?.entry && <ConditionRow label="Einstieg" value={block.entry} />}
          {block?.launch_area && <ConditionRow label="Start-/Landefläche" value={block.launch_area} />}
          {block?.level?.length ? (
            <ConditionRow label="Level" value={block.level.map(levelLabel).join(", ")} />
          ) : null}
          {block?.discipline?.length ? (
            <ConditionRow label="Disziplin" value={block.discipline.map(styleLabel).join(", ")} />
          ) : null}
          {block?.hazards && <ConditionRow label="Hindernisse" value={block.hazards} />}
          {block?.local_rules && <ConditionRow label="Lokale Regeln" value={block.local_rules} />}
          {block?.notes && <p className="pt-1 text-caption text-muted">{block.notes}</p>}
        </div>
      )}
    </div>
  );
}

export default function SpotVariants({ spot }: { spot: Spot }) {
  const conditions = spot.variantConditions ?? null;
  // Only wind-/kitesurf split into variants; show a group per selected sport.
  const groups = (spot.sports ?? [])
    .filter((sport) => (SPORT_VARIANTS[sport] ?? []).length > 0)
    .map((sport) => ({ sport, keys: SPORT_VARIANTS[sport] as readonly string[] }));

  if (groups.length === 0) return null;

  return (
    <section aria-label="Varianten und Eignung" className="mt-8 lg:mt-12">
      <h2 className="text-ui font-semibold text-ink">Varianten</h2>
      <div className="mt-4 space-y-4">
        {groups.map(({ sport, keys }) => (
          <div key={sport}>
            <h3 className="text-caption font-semibold uppercase tracking-wide text-muted">
              {sportLabel(sport)}
            </h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {keys.map((key) => (
                <VariantCard
                  key={key}
                  variantKey={key}
                  block={conditions?.[key]}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
