import { Button, Field, Input, Select } from "../../components/ui";
import type { BoardType, GearCatalogClaim, GearCatalogItem, GearKind, SportKey } from "../../lib/account";

export interface QuiverDraft {
  clientId: string;
  id?: string;
  sport: SportKey;
  kind: GearKind;
  size: number | null;
  boardType: BoardType | null;
  catalogSizeVariantId: string | null;
  catalogColorVariantId: string | null;
  catalogItem?: GearCatalogItem | null;
  active: boolean;
  sortOrder: number;
}

const BOARD_LABELS: Record<BoardType, string> = {
  twintip: "Twintip",
  surfboard: "Surfboard",
  foil: "Foilboard",
  bigair_twintip: "Big-Air-Twintip",
};

function draftId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `draft-${Date.now()}-${Math.random()}`;
}

export default function QuiverEditor({
  items,
  catalog = [],
  catalogError = null,
  onChange,
  disabled = false,
}: {
  items: QuiverDraft[];
  catalog?: GearCatalogItem[];
  catalogError?: string | null;
  onChange: (items: QuiverDraft[]) => void;
  disabled?: boolean;
}) {
  const kites = items.filter((item) => item.kind === "kite");
  const board = items.find((item) => item.kind === "board" || item.kind === "foil");

  const updateKite = (clientId: string, size: number | null) => {
    onChange(items.map((item) => item.clientId === clientId ? {
      ...item, size, catalogSizeVariantId: null, catalogColorVariantId: null, catalogItem: null,
    } : item));
  };

  const selectCatalogItem = (clientId: string, catalogSizeVariantId: string | null) => {
    const selected = catalog.find((item) => item.catalogSizeVariantId === catalogSizeVariantId) ?? null;
    onChange(items.map((item) => item.clientId === clientId ? {
      ...item,
      catalogSizeVariantId: selected?.catalogSizeVariantId ?? null,
      catalogColorVariantId: null,
      catalogItem: selected,
      size: selected?.size.value ?? item.size,
    } : item));
  };

  const selectColor = (clientId: string, catalogColorVariantId: string | null) => {
    onChange(items.map((item) => item.clientId === clientId
      ? { ...item, catalogColorVariantId }
      : item));
  };

  const removeKite = (clientId: string) => {
    onChange(items.filter((item) => item.clientId !== clientId));
  };

  const addKite = () => {
    onChange([...items, {
      clientId: draftId(), sport: "kitesurf", kind: "kite", size: null,
      boardType: null, catalogSizeVariantId: null, catalogColorVariantId: null,
      catalogItem: null, active: true, sortOrder: kites.length,
    }]);
  };

  const setBoard = (boardType: BoardType | null) => {
    const withoutBoard = items.filter((item) => item.kind !== "board" && item.kind !== "foil");
    if (!boardType) {
      onChange(withoutBoard);
      return;
    }
    onChange([...withoutBoard, {
      clientId: board?.clientId ?? draftId(), id: board?.id,
      sport: "kitesurf", kind: "board", size: null, boardType,
      catalogSizeVariantId: null, catalogColorVariantId: null, catalogItem: null,
      active: true, sortOrder: withoutBoard.length,
    }]);
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        {kites.map((kite, index) => (
          <div key={kite.clientId} className="border-b border-line pb-6 last:border-b-0">
            <div className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <Field label={`Kite ${index + 1}`} hint="Katalogprodukt oder freie Größe">
                <Select
                  aria-label={`Produkt für Kite ${index + 1}`}
                  value={kite.catalogSizeVariantId ?? ""}
                  disabled={disabled || catalog.length === 0}
                  onChange={(event) => selectCatalogItem(kite.clientId, event.target.value || null)}
                >
                  <option value="">Freie Größenangabe</option>
                  {catalog.map((entry) => (
                    <option key={entry.catalogSizeVariantId} value={entry.catalogSizeVariantId}>
                      {entry.brand.name} {entry.name} · {entry.season} · {entry.size.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Button
                variant="ghost"
                disabled={disabled}
                onClick={() => removeKite(kite.clientId)}
                aria-label={`Kite ${index + 1} entfernen`}
              >
                Entfernen
              </Button>
            </div>
            {!kite.catalogSizeVariantId && (
              <div className="mt-3 max-w-48">
                <Field label="Größe">
                  <div className="relative">
                    <Input
                      aria-label={`Größe Kite ${index + 1} in Quadratmetern`}
                      type="number" min="1" max="30" step="0.5" inputMode="decimal"
                      value={kite.size ?? ""} disabled={disabled}
                      onChange={(event) => updateKite(
                        kite.clientId,
                        event.target.value === "" ? null : Number(event.target.value),
                      )}
                      className="pr-12"
                    />
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ui text-muted">m²</span>
                  </div>
                </Field>
              </div>
            )}
            {kite.catalogSizeVariantId && (
              <CatalogSelection
                entry={catalog.find((entry) => entry.catalogSizeVariantId === kite.catalogSizeVariantId) ?? kite.catalogItem ?? null}
                selectedColorId={kite.catalogColorVariantId}
                onColorChange={(colorId) => selectColor(kite.clientId, colorId)}
                disabled={disabled}
              />
            )}
          </div>
        ))}
        {kites.length === 0 && (
          <p className="text-ui text-muted">Füge mindestens einen Kite hinzu.</p>
        )}
        {catalogError && <p role="status" className="text-ui text-warning">{catalogError}</p>}
        <Button variant="secondary" disabled={disabled} onClick={addKite}>
          Kite hinzufügen
        </Button>
      </div>

      <Field label="Board-Typ" hint="Optional">
        <Select
          value={board?.boardType ?? ""}
          disabled={disabled}
          onChange={(event) => setBoard((event.target.value || null) as BoardType | null)}
        >
          <option value="">Nicht angegeben</option>
          {Object.entries(BOARD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </Select>
      </Field>
    </div>
  );
}

function claimValue(claim: GearCatalogClaim): string {
  if ("min" in claim.value && "max" in claim.value) {
    return `${claim.value.min}–${claim.value.max}${claim.unit ? ` ${claim.unit}` : ""}`;
  }
  if ("code" in claim.value && "name" in claim.value) {
    return `${claim.value.code} · ${claim.value.name}`;
  }
  return `${claim.value.value ?? "Unbekannt"}${claim.unit ? ` ${claim.unit}` : ""}`;
}

const CLAIM_LABELS: Record<string, string> = {
  model_year: "Modelljahr",
  weight_without_bag: "Gewicht ohne Tasche",
  intended_use: "Einsatz",
  available_size: "Verfügbare Größe",
  edition: "Edition",
  strut_count: "Struts",
  aspect_ratio: "Aspect Ratio",
  kite_shape: "Kite-Form",
  profile_depth: "Profiltiefe",
  projected_area: "Projizierte Fläche",
  flat_span: "Flache Spannweite",
  projected_span: "Projizierte Spannweite",
  arc_ratio: "Bogenverhältnis",
  chord_depth: "Profiltiefe",
  tip_sweep: "Tip-Sweep",
  leading_edge_diameter: "Leading-Edge-Durchmesser",
  bar_pressure: "Bardruck",
  depower: "Depower",
  skill_level: "Fahrkönnen",
  canopy_material: "Tuchmaterial",
  leading_edge_material: "Leading-Edge-Material",
  valve_system: "Ventilsystem",
  one_pump_system: "One-Pump-System",
  bar_compatibility: "Bar-Kompatibilität",
  line_length: "Leinenlänge",
  colorway: "Farbvariante",
};

const CLAIM_GROUPS: Array<{ key: GearCatalogClaim["group"]; label: string }> = [
  { key: "identity", label: "Modell" },
  { key: "dimensions", label: "Maße und Gewicht" },
  { key: "geometry", label: "Geometrie" },
  { key: "construction", label: "Konstruktion" },
  { key: "performance", label: "Fahreigenschaften" },
  { key: "compatibility", label: "Kompatibilität" },
  { key: "appearance", label: "Ausführung" },
  { key: "other", label: "Weitere Angaben" },
];

const CATEGORY_LABELS: Record<string, string> = {
  kite: "Kite", bar: "Bar", line_set: "Leinenset", kiteboard: "Kiteboard",
  surfboard: "Surfboard", harness: "Trapez", wetsuit: "Neoprenanzug",
  wing: "Wing", foil: "Foil", foil_component: "Foil-Komponente",
};

const DISCIPLINE_LABELS: Record<string, string> = {
  all_round: "Allround", freeride: "Freeride", big_air: "Big Air", wave: "Wave",
  freestyle: "Freestyle", foil: "Foil", race: "Race", school: "Schulung",
};

const CONDITION_LABELS: Record<string, string> = {
  all_conditions: "alle Bedingungen", light_wind: "Leichtwind",
  moderate_wind: "mittlerer Wind", strong_wind: "Starkwind", waves: "Welle",
  flat_water: "Flachwasser", gusty: "böiger Wind",
};

const SUITABILITY_LABELS: Record<string, string> = {
  designed_for: "dafür entwickelt", suitable: "geeignet", limited: "eingeschränkt",
  not_recommended: "nicht empfohlen",
};

const RELATION_LABELS: Record<string, string> = {
  requires: "benötigt", compatible: "kompatibel", recommended: "empfohlen",
  incompatible: "nicht kompatibel",
};

function CatalogSelection({
  entry,
  selectedColorId,
  onColorChange,
  disabled,
}: {
  entry: GearCatalogItem | null;
  selectedColorId: string | null;
  onColorChange: (colorId: string | null) => void;
  disabled: boolean;
}) {
  if (!entry) {
    return <p role="status" className="mt-3 text-ui text-warning">Produktdetails fehlen. Die Auswahl bleibt gespeichert, bis der Katalog wieder verfügbar ist.</p>;
  }
  const sources = Array.from(new Map(
    [
      ...entry.specifications,
      ...(entry.colors.find((color) => color.id === selectedColorId)?.specifications ?? []),
      ...entry.compatibility,
      ...entry.useProfiles,
    ].map((item) => [item.source.url, item.source]),
  ).values());
  const specifications = [
    ...entry.specifications,
    ...(entry.colors.find((color) => color.id === selectedColorId)?.specifications ?? []),
  ];
  const specificationGroups = CLAIM_GROUPS.map((group) => ({
    ...group,
    claims: specifications.filter((claim) => claim.group === group.key),
  })).filter((group) => group.claims.length > 0);
  return (
    <article className="mt-4 rounded-card bg-band p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-title font-semibold text-ink">{entry.brand.name} {entry.name}</h3>
              <p className="mt-1 text-ui text-muted">{entry.season} · {entry.size.label}</p>
            </div>
            <span className="rounded-full bg-surface px-3 py-1 text-caption font-semibold text-muted">
              {CATEGORY_LABELS[entry.category] ?? entry.category}
            </span>
          </div>

          {entry.colors.length > 0 && (
            <div className="mt-5 max-w-64">
              <Field label="Farbvariante" hint="Optional">
                <Select
                  value={selectedColorId ?? ""}
                  disabled={disabled}
                  onChange={(event) => onColorChange(event.target.value || null)}
                >
                  <option value="">Nicht angegeben</option>
                  {entry.colors.map((color) => (
                    <option key={color.id} value={color.id}>{color.code}{color.name ? ` · ${color.name}` : ""}</option>
                  ))}
                </Select>
              </Field>
            </div>
          )}

          {entry.useProfiles.length > 0 && (
            <section className="mt-5" aria-labelledby="gear-use-profiles">
              <h4 id="gear-use-profiles" className="text-caption font-semibold text-muted">Einsatzbereiche</h4>
              <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                {entry.useProfiles.map((profile) => (
                  <li key={`${profile.sport}-${profile.discipline}-${profile.condition}`} className="text-ui text-ink">
                    <span className="font-semibold">{DISCIPLINE_LABELS[profile.discipline] ?? profile.discipline}</span>
                    {` · ${CONDITION_LABELS[profile.condition] ?? profile.condition}`}
                    {` · ${SUITABILITY_LABELS[profile.suitability] ?? profile.suitability}`}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {entry.compatibility.length > 0 && (
            <section className="mt-5" aria-labelledby="gear-compatibility">
              <h4 id="gear-compatibility" className="text-caption font-semibold text-muted">Kompatibilität</h4>
              <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                {entry.compatibility.map((item) => (
                  <li key={`${item.targetCategory}-${item.relation}`} className="text-ui text-ink">
                    <span className="font-semibold">
                      {item.targetProduct
                        ? `${item.targetProduct.brand.name} ${item.targetProduct.name} ${item.targetProduct.season}`
                        : CATEGORY_LABELS[item.targetCategory] ?? item.targetCategory}
                    </span>
                    {` · ${RELATION_LABELS[item.relation] ?? item.relation}`}
                    {typeof item.specification.system === "string" && ` · ${item.specification.system}`}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {specificationGroups.length > 0 ? (
            <div className="mt-5 space-y-5">
              {specificationGroups.map((group) => (
                <section key={group.key} aria-labelledby={`gear-specs-${group.key}`}>
                  <h4 id={`gear-specs-${group.key}`} className="text-caption font-semibold text-muted">
                    {group.label}
                  </h4>
                  <dl className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2">
                    {group.claims.map((claim) => (
                      <div key={`${claim.field}-${claim.source.url}`}>
                        <dt className="text-caption text-muted">{CLAIM_LABELS[claim.field] ?? claim.field}</dt>
                        <dd className="text-ui font-semibold text-ink">{claimValue(claim)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
          ) : (
            <p className="mt-5 text-ui text-muted">Noch keine geprüften technischen Angaben.</p>
          )}

          <div className="mt-5 border-t border-line pt-4">
            <p className="text-caption text-muted">Quellen geprüft; Herstellerbilder und Logos wurden nicht übernommen.</p>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
              {sources.map((source) => (
                <a
                  key={source.url}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-caption font-semibold text-accent underline decoration-line underline-offset-4 hover:text-accent-hover"
                >
                  {source.publisher}: {source.title}
                </a>
              ))}
            </div>
          </div>
    </article>
  );
}
