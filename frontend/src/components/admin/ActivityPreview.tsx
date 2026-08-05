import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { getAdminSpot, type ActivityItem, type SpotRead } from "../../lib/api";
import {
  actionLabel,
  facilityLabel,
  gapLabel,
  levelLabel,
  sportLabel,
  styleList,
  waterCharacterLabel,
} from "../../lib/labels";
import type { FacilityKind } from "../../lib/api";
import Modal from "../ui/Modal";
import { createAdminReturnState } from "../../lib/adminNavigation";

/**
 * Activity preview. Clicking a spot activity opens a read-only view laid out
 * like the spot editor — the same sections in the same order — so it reads as
 * "the form". The fields the audit recorded as changed keep the form order but
 * get a green stroke + a "geändert" badge.
 *
 * The audit only stores WHICH fields changed (not the old values), so this
 * shows the spot's CURRENT values with the changed ones marked — no true
 * before/after diff (that would need the audit to store values).
 */

function facilitiesSummary(f: SpotRead["facilities"]): string {
  if (!f) return "—";
  const on = (Object.keys(f) as FacilityKind[]).filter((k) => f[k]?.available);
  return on.length ? on.map(facilityLabel).join(", ") : "—";
}

interface FieldDef {
  key: string;
  label: string;
  value: (s: SpotRead) => ReactNode;
}

interface Section {
  title: string;
  fields: FieldDef[];
}

// The spot editor's sections, in editor order. `key` matches the audit field
// keys (see app/admin/team.py::_changed_fields) so we can flag what changed.
const SECTIONS: Section[] = [
  {
    title: "Grunddaten",
    fields: [{ key: "name", label: "Name", value: (s) => s.name || "—" }],
  },
  {
    title: "Sportarten & Eigenschaften",
    fields: [
      { key: "sports", label: "Sportarten", value: (s) => s.sports.map(sportLabel).join(", ") || "—" },
      { key: "level", label: "Level", value: (s) => (s.level ?? []).map(levelLabel).join(", ") || "—" },
      { key: "water_type", label: "Gewässerart", value: (s) => (s.water_type ?? []).join(", ") || "—" },
      { key: "bottom_type", label: "Untergrund", value: (s) => s.bottom_type ?? "—" },
      { key: "water_character", label: "Wasserart", value: (s) => (s.water_character ?? []).map(waterCharacterLabel).join(", ") || "—" },
      { key: "style", label: "Fahrstil", value: (s) => styleList(s.style) || "—" },
    ],
  },
  {
    title: "Ausstattung",
    fields: [{ key: "facilities", label: "Ausstattung", value: (s) => facilitiesSummary(s.facilities) }],
  },
  {
    title: "Redaktionell",
    fields: [
      { key: "editorial.description", label: "Beschreibung", value: (s) => s.editorial?.description ?? "—" },
      {
        key: "editorial.usable_wind_directions",
        label: "Nutzbare Windrichtungen",
        value: (s) => {
          const w = s.editorial?.usable_wind_directions;
          return Array.isArray(w) ? w.join(", ") || "—" : w ?? "—";
        },
      },
    ],
  },
  {
    title: "Medien & Daten",
    fields: [
      { key: "image", label: "Titelbild", value: (s) => (s.image?.url ? "gesetzt" : "—") },
      { key: "climatology", label: "Klimatologie", value: (s) => (s.climatology?.weeks ? "vorhanden" : "—") },
    ],
  },
];

const KNOWN = new Set(SECTIONS.flatMap((sec) => sec.fields.map((f) => f.key)));

// Best-effort value for a changed key that isn't in the curated list above.
function genericValue(s: SpotRead, key: string): string {
  let v: unknown;
  if (key.startsWith("editorial.")) v = s.editorial?.[key.slice("editorial.".length)];
  else v = (s as unknown as Record<string, unknown>)[key];
  if (v == null) return "—";
  if (Array.isArray(v)) return v.join(", ") || "—";
  if (typeof v === "object") return "geändert";
  return String(v);
}

function FieldRow({
  label,
  changed,
  children,
}: {
  label: string;
  changed: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={`rounded-lg px-3 py-2 ${
        changed
          ? "border border-green/40 bg-green/10 ring-1 ring-green/30"
          : "border border-line bg-white"
      }`}
    >
      <dt className="flex items-center gap-2 text-caption text-muted">
        {label}
        {changed && (
          <span className="rounded-full bg-green/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green">
            geändert
          </span>
        )}
      </dt>
      <dd className="mt-0.5 whitespace-pre-wrap break-words text-label text-ink">{children}</dd>
    </div>
  );
}

export default function ActivityPreview({
  item,
  onClose,
}: {
  item: ActivityItem | null;
  onClose: () => void;
}) {
  const location = useLocation();
  const editorState = createAdminReturnState(location, "Aktivität");
  const open = item !== null && item.kind === "spot" && !!item.target_id;
  const [spot, setSpot] = useState<SpotRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !item?.target_id) return;
    setSpot(null);
    setError(null);
    setLoading(true);
    getAdminSpot(item.target_id)
      .then(setSpot)
      .catch(() => setError("Spot konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [open, item?.target_id]);

  if (!open || !item) return null;

  const changed = new Set(item.fields);
  // Changed keys the curated sections don't cover (shown in an extra section).
  const extras = item.fields.filter((k) => !KNOWN.has(k));

  return (
    <Modal open={open} onClose={onClose} labelledBy="activity-preview-title">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="activity-preview-title" className="text-ui font-semibold text-ink">
            {item.target ?? "Spot"}
          </h2>
          <p className="mt-0.5 text-caption text-muted">
            <span className="font-medium text-ink">{item.actor ?? "—"}</span> ·{" "}
            {actionLabel(item.action) || item.label} ·{" "}
            {item.at ? new Date(item.at).toLocaleString("de-DE") : ""}
          </p>
        </div>
        {item.target_id && (
          <Link
            to={`/admin/spot/${item.target_id}/edit`}
            state={editorState}
            className="shrink-0 rounded-lg border border-teal/30 px-3 py-1.5 text-caption font-medium text-teal hover:bg-teal/5"
          >
            Öffnen →
          </Link>
        )}
      </div>

      {changed.size > 0 && (
        <p className="mt-3 flex items-center gap-1.5 text-caption text-muted">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-green" />
          Grün = bei dieser Änderung bearbeitet
        </p>
      )}

      <div className="mt-3 max-h-[55vh] space-y-4 overflow-y-auto pr-1">
        {loading ? (
          <p className="py-6 text-center text-label text-muted">Lädt…</p>
        ) : error ? (
          <p className="py-6 text-center text-label text-red-600">{error}</p>
        ) : spot ? (
          <>
            {SECTIONS.map((section) => (
              <section key={section.title}>
                <p className="mb-1.5 text-caption font-semibold uppercase tracking-wide text-muted">
                  {section.title}
                </p>
                <dl className="space-y-1.5">
                  {section.fields.map((f) => (
                    <FieldRow key={f.key} label={f.label} changed={changed.has(f.key)}>
                      {f.value(spot)}
                    </FieldRow>
                  ))}
                </dl>
              </section>
            ))}
            {extras.length > 0 && (
              <section>
                <p className="mb-1.5 text-caption font-semibold uppercase tracking-wide text-muted">
                  Weitere Änderungen
                </p>
                <dl className="space-y-1.5">
                  {extras.map((k) => (
                    <FieldRow key={k} label={gapLabel(k)} changed>
                      {genericValue(spot, k)}
                    </FieldRow>
                  ))}
                </dl>
              </section>
            )}
          </>
        ) : null}
      </div>
    </Modal>
  );
}
