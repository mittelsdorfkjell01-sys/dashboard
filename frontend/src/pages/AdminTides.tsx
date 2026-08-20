import { useEffect, useState } from "react";
import { ApiError, getAdminSpots, type AdminSpotSummary } from "../lib/api";
import { PageHeader, SearchInput } from "../components/admin/ui";
import { countryName } from "../lib/flags";
import Modal from "../components/ui/Modal";
import TideAdminPanel from "../components/admin/TideAdminPanel";

/**
 * Standalone "Tidenkorrektur" tab: every spot in one list, click a row to
 * open its correction panel in a dialog. Moved out of the spot form so
 * daily tide work doesn't require opening the whole editor.
 */
export default function AdminTides() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<AdminSpotSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<AdminSpotSummary | null>(null);

  useEffect(() => {
    setError(null);
    getAdminSpots({ limit: 500, sort: "name" })
      .then((result) => setItems(result.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Spots konnten nicht geladen werden."));
  }, []);

  const filtered = items.filter((s) => {
    if (!q.trim()) return true;
    const needle = q.trim().toLowerCase();
    return s.name.toLowerCase().includes(needle) || (s.region_name ?? "").toLowerCase().includes(needle);
  });

  return (
    <div>
      <PageHeader title="Tidenkorrektur" />
      <div className="mb-5 max-w-sm">
        <SearchInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Spot oder Region suchen …" />
      </div>
      {error && <p role="alert" className="mb-4 text-admin-danger">{error}</p>}
      <div className="overflow-hidden rounded-md border border-admin-border">
        <ul>
          {filtered.map((spot) => (
            <li key={spot.id} className="border-b border-admin-border last:border-b-0">
              <button
                type="button"
                onClick={() => setActive(spot)}
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-ui text-admin-fg transition-colors hover:bg-admin-hover"
              >
                <span className="min-w-0 truncate font-medium">{spot.name}</span>
                <span className="shrink-0 text-caption text-admin-muted">
                  {[spot.region_name, countryName(spot.region_country ?? undefined)].filter(Boolean).join(" · ") || "Ohne Region"}
                </span>
              </button>
            </li>
          ))}
          {!error && filtered.length === 0 && (
            <li className="px-4 py-6 text-center text-label text-admin-muted">Keine Spots gefunden.</li>
          )}
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
              Gezeiten-Korrektur — {active.name}
            </h2>
            <TideAdminPanel spotId={active.id} />
          </>
        )}
      </Modal>
    </div>
  );
}
