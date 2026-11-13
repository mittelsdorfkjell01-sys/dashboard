import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getTideRolloutQueue,
  type TideRolloutItem,
  type TideRolloutStatus,
} from "../lib/api/tides";
import { ApiError } from "../lib/api/client";
import { Badge, PageHeader, SearchInput, type BadgeTone } from "../components/admin/ui";
import { countryName } from "../lib/flags";
import Modal from "../components/ui/Modal";
import TideAdminPanel from "../components/admin/TideAdminPanel";

/**
 * Europe rollout queue: only published marine spots, ordered into explicit
 * calculation, anchor-review and publication states.
 */
export default function AdminTides() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | "review" | "processing" | "private" | "public" | "problems">("all");
  const [items, setItems] = useState<TideRolloutItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<TideRolloutItem | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    return getTideRolloutQueue()
      .then((result) => setItems(result.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Tide-Review-Queue konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { void reload(); }, [reload]);

  const filtered = useMemo(() => items.filter((item) => {
    const needle = q.trim().toLowerCase();
    const matchesText = !needle
      || item.spot_name.toLowerCase().includes(needle)
      || (item.region_name ?? "").toLowerCase().includes(needle);
    if (!matchesText) return false;
    if (filter === "review") return item.status === "anchor_review";
    if (filter === "processing") return item.status === "processing";
    if (filter === "private") return item.status === "reviewed_private";
    if (filter === "public") return item.status === "public";
    if (filter === "problems") return PROBLEM_STATUSES.has(item.status);
    return true;
  }), [filter, items, q]);

  const counts = useMemo(() => ({
    all: items.length,
    review: items.filter((item) => item.status === "anchor_review").length,
    processing: items.filter((item) => item.status === "processing").length,
    private: items.filter((item) => item.status === "reviewed_private").length,
    public: items.filter((item) => item.status === "public").length,
    problems: items.filter((item) => PROBLEM_STATUSES.has(item.status)).length,
  }), [items]);

  return (
    <div>
      <PageHeader title="FES-Tide Europa" />
      <p className="mb-5 max-w-3xl text-ui text-admin-fg2">
        Der Worker berechnet astronomische Tide zunächst privat. Prüfe Modellanker und Warnungen, bevor ein Spot veröffentlicht wird.
      </p>
      <div className="mb-4 max-w-sm">
        <SearchInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Spot oder Region suchen …" />
      </div>
      <div className="mb-5 flex flex-wrap gap-2" aria-label="Tide-Queue filtern">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            type="button"
            aria-pressed={filter === item.key}
            onClick={() => setFilter(item.key)}
            className={`min-h-11 rounded-full border px-3 text-caption font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-admin-primary ${
              filter === item.key
                ? "border-admin-primary bg-admin-primary text-admin-primary-fg"
                : "border-admin-border bg-admin-surface text-admin-fg2 hover:bg-admin-hover"
            }`}
          >
            {item.label} · {counts[item.key]}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="mb-4 text-admin-danger">{error}</p>}
      <div className="overflow-hidden rounded-md border border-admin-border">
        <ul>
          {filtered.map((item) => (
            <li key={item.spot_id} className="border-b border-admin-border last:border-b-0">
              <button
                type="button"
                onClick={() => setActive(item)}
                className="grid min-h-14 w-full gap-2 px-4 py-3 text-left text-ui text-admin-fg transition-colors hover:bg-admin-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-admin-primary sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center"
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{item.spot_name}</span>
                  <span className="mt-0.5 block text-caption text-admin-muted sm:hidden">
                    {[item.region_name, countryName(item.country ?? undefined)].filter(Boolean).join(" · ") || "Ohne Region"}
                  </span>
                </span>
                <span className="hidden shrink-0 text-caption text-admin-muted sm:block">
                  {[item.region_name, countryName(item.country ?? undefined)].filter(Boolean).join(" · ") || "Ohne Region"}
                </span>
                <Badge tone={STATUS_META[item.status].tone}>{STATUS_META[item.status].label}</Badge>
              </button>
            </li>
          ))}
          {!error && !loading && filtered.length === 0 && (
            <li className="px-4 py-8 text-center text-label text-admin-muted">Keine Spots in diesem Zustand.</li>
          )}
          {loading && <li className="px-4 py-8 text-center text-label text-admin-muted">Tide-Queue wird geladen.</li>}
        </ul>
      </div>

      <Modal
        open={active != null}
        onClose={() => setActive(null)}
        labelledBy="tide-correction-title"
        cardClassName="max-w-xl rounded-lg bg-admin-surface p-6"
      >
        {active && (
          <>
            <h2 id="tide-correction-title" className="mb-4 text-ui font-semibold text-admin-fg">
              FES-Tide — {active.spot_name}
            </h2>
            <TideAdminPanel spotId={active.spot_id} onChanged={reload} />
          </>
        )}
      </Modal>
    </div>
  );
}

const PROBLEM_STATUSES = new Set<TideRolloutStatus>([
  "missing_profile", "disabled", "failed", "invalid", "needs_anchor",
]);

const STATUS_META: Record<TideRolloutStatus, { label: string; tone: BadgeTone }> = {
  missing_profile: { label: "Noch nicht eingeplant", tone: "neutral" },
  disabled: { label: "Deaktiviert", tone: "neutral" },
  processing: { label: "In Berechnung", tone: "info" },
  failed: { label: "Berechnung fehlgeschlagen", tone: "danger" },
  invalid: { label: "Anker ungültig", tone: "danger" },
  anchor_review: { label: "Anker prüfen", tone: "warning" },
  reviewed_private: { label: "Geprüft · privat", tone: "primary" },
  public: { label: "Veröffentlicht", tone: "success" },
  needs_anchor: { label: "Anker fehlt", tone: "warning" },
};

const FILTERS = [
  { key: "all", label: "Alle" },
  { key: "review", label: "Zu prüfen" },
  { key: "processing", label: "In Arbeit" },
  { key: "private", label: "Geprüft" },
  { key: "public", label: "Live" },
  { key: "problems", label: "Probleme" },
] as const;
