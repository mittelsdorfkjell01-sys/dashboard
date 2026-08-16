// Admin regions (Sprint B): list with per-status spot counts and create a
// region. Like the spot list, each card only links to the editor — clicking
// anywhere on the card opens it, everything else lives in the editor itself.

import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  ApiError,
  getAdminRegions,
  type AdminRegionEntry,
} from "../lib/api";
import { PageHeader, Badge, ButtonLink, SearchInput } from "../components/admin/ui";
import { createAdminReturnState } from "../lib/adminNavigation";
import { PlusIcon } from "../lib/icons";

export default function AdminRegions() {
  const location = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [searchText, setSearchText] = useState(q);
  const editorState = createAdminReturnState(location, "Regionen");
  const [entries, setEntries] = useState<AdminRegionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await getAdminRegions(q || undefined));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setSearchText(q), [q]);
  useEffect(() => {
    if (searchText === q) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(params);
      if (searchText.trim()) next.set("q", searchText.trim());
      else next.delete("q");
      setParams(next);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchText, q, params, setParams]);

  return (
    <div>
      <PageHeader
        title="Regionen"
        actions={
          <ButtonLink variant="primary" to="/admin/region/new" state={editorState}>
            <PlusIcon className="text-[16px]" /> Region anlegen
          </ButtonLink>
        }
      />

      <div className="mt-4 max-w-xl">
        <label className="block text-label font-medium text-admin-fg">
          Suche
          <SearchInput
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Region oder Land suchen …"
            className="mt-1 w-full"
          />
        </label>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
        >
          {error}
        </div>
      )}

      {/* Card list: single column, two columns on wide desktops (2xl) so the
          cards don't stretch into a huge empty middle. */}
      <div className="mt-8 grid grid-cols-1 gap-3 2xl:grid-cols-2">
        {loading ? (
          <div className="text-ui text-admin-muted">Lädt…</div>
        ) : entries.length === 0 ? (
          <div className="rounded-lg border border-dashed border-admin-border bg-admin-surface p-6 text-center">
            <p className="text-ui text-admin-muted">
              {q ? `Keine Region für „${q}“ gefunden.` : "Noch keine Regionen vorhanden."}
            </p>
            <ButtonLink variant="primary" className="mt-4" to="/admin/region/new" state={editorState}>
              <PlusIcon className="text-[16px]" /> Region anlegen
            </ButtonLink>
          </div>
        ) : (
          entries.map((entry) => (
            <RegionCard
              key={entry.region.id}
              entry={entry}
              onOpen={() =>
                navigate(`/admin/region/${entry.region.id}/edit`, { state: editorState })
              }
              editorState={editorState}
            />
          ))
        )}
      </div>
    </div>
  );
}

function RegionCard({
  entry,
  onOpen,
  editorState,
}: {
  entry: AdminRegionEntry;
  onOpen: () => void;
  editorState: ReturnType<typeof createAdminReturnState>;
}) {
  const { region, spot_counts } = entry;

  return (
    <div
      onClick={onOpen}
      className="group cursor-pointer rounded-lg border border-admin-border bg-admin-surface p-4 transition-colors hover:border-admin-border-strong sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-admin-fg group-hover:text-admin-primary">
            {region.name}
            {region.country && (
              <span className="ml-2 text-label font-normal text-admin-muted">
                {region.country}
              </span>
            )}
          </div>
          <div className="mt-1.5 flex gap-3 text-caption text-admin-muted">
            <span className="admin-mono text-admin-success">{spot_counts.published}</span> live
            <span className="admin-mono">{spot_counts.draft}</span> Entwurf
            <span className="admin-mono">{spot_counts.archived}</span> archiviert
          </div>
        </div>
        <div className="flex items-center gap-2">
          {region.image?.url ? (
            <Badge tone="success">Bild gesetzt</Badge>
          ) : (
            <Badge tone="neutral">Kein Bild</Badge>
          )}
          <ButtonLink
            variant="secondary"
            to={`/admin/region/${region.id}/edit`}
            state={editorState}
            onClick={(event) => event.stopPropagation()}
          >
            Bearbeiten
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
