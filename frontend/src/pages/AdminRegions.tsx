// Admin regions (Sprint B): list with per-status spot counts and create a
// region. Like the spot list, each card only links to the editor — clicking
// anywhere on the card opens it, everything else lives in the editor itself.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  ApiError,
  createRegion,
  getAdminRegions,
  type AdminRegionEntry,
} from "../lib/api";
import { Button, Input } from "../components/ui";
import Modal from "../components/ui/Modal";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import { PageHeader, Badge } from "../components/admin/ui";
import { createAdminReturnState } from "../lib/adminNavigation";
import { PlusIcon } from "../lib/icons";
import DuplicateWarningDialog from "../components/admin/DuplicateWarningDialog";
import {
  parseDuplicateConflict,
  type DuplicateConflict,
} from "../lib/duplicateConflicts";
import {
  useFormDirty,
  useUnsavedChangesGuard,
} from "../lib/useUnsavedChangesGuard";
import UnsavedChangesDialog from "../components/admin/UnsavedChangesDialog";

export default function AdminRegions() {
  const { blocker, setDirty } = useUnsavedChangesGuard();
  const location = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [searchText, setSearchText] = useState(q);
  const editorState = createAdminReturnState(location, "Regionen");
  const [entries, setEntries] = useState<AdminRegionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createDirty, setCreateDirty] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => setDirty("create-region", createDirty), [createDirty, setDirty]);

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

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3000);
  };

  return (
    <div>
      <PageHeader
        title="Regionen"
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <PlusIcon className="text-[16px]" /> Region anlegen
          </Button>
        }
      />

      <div className="mt-4 flex max-w-xl items-end gap-2">
        <label className="min-w-0 flex-1 text-label font-medium text-admin-fg">
          Region oder Land suchen
          <Input
            type="search"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            className="mt-1 w-full"
          />
        </label>
        {searchText && (
          <Button type="button" variant="ghost" onClick={() => setSearchText("")}>
            Löschen
          </Button>
        )}
      </div>

      {notice && (
        <div
          role="status"
          className="mt-4 rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label font-medium text-admin-success"
        >
          {notice}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
        >
          {error}
        </div>
      )}

      {createOpen && (
        <Modal
          open
          onClose={() => createDirty ? setConfirmDiscard(true) : setCreateOpen(false)}
          labelledBy="create-region-title"
        >
          <CreateRegionForm
            onDirtyChange={setCreateDirty}
            onCancel={() => createDirty ? setConfirmDiscard(true) : setCreateOpen(false)}
            onCreated={async (name) => {
              setCreateDirty(false);
              setCreateOpen(false);
              flash(`Region „${name}" angelegt.`);
              await load();
            }}
            onError={setError}
          />
        </Modal>
      )}
      <ConfirmDialog
        open={confirmDiscard}
        title="Eingaben verwerfen?"
        message="Die noch nicht gespeicherten Angaben zur Region gehen verloren."
        confirmText="Verwerfen"
        onCancel={() => setConfirmDiscard(false)}
        onConfirm={() => {
          setConfirmDiscard(false);
          setCreateDirty(false);
          setCreateOpen(false);
        }}
      />
      <UnsavedChangesDialog blocker={blocker} />

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
            <Button className="mt-4" onClick={() => setCreateOpen(true)}>
              <PlusIcon className="text-[16px]" /> Region anlegen
            </Button>
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
          <Link
            to={`/admin/region/${region.id}/edit`}
            state={editorState}
            onClick={(event) => event.stopPropagation()}
            className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
          >
            Bearbeiten
          </Link>
        </div>
      </div>
    </div>
  );
}

function CreateRegionForm({
  onCreated,
  onError,
  onCancel,
  onDirtyChange,
}: {
  onCreated: (name: string) => void | Promise<void>;
  onError: (msg: string) => void;
  onCancel: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [busy, setBusy] = useState(false);
  const [duplicateConflict, setDuplicateConflict] = useState<DuplicateConflict | null>(null);
  const dirty = useFormDirty({ name, country }, { name: "", country: "" });

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  const save = async (allowDuplicate = false) => {
    setBusy(true);
    try {
      // No coordinates: the backend geocodes the name → centre + bounds.
      await createRegion({
        name: name.trim(),
        country: country.trim() || undefined,
        allow_duplicate: allowDuplicate,
      });
      setName("");
      setCountry("");
      onDirtyChange(false);
      await onCreated(name.trim());
    } catch (err) {
      const duplicate = parseDuplicateConflict(err);
      if (duplicate) {
        setDuplicateConflict(duplicate);
        return;
      }
      onError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void save(false);
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <h2 id="create-region-title" className="text-[18px] font-semibold text-admin-fg">
        Region anlegen
      </h2>
      <div>
        <label htmlFor="create-region-name" className="text-label font-medium text-admin-fg">
          Name
        </label>
        <Input
          id="create-region-name"
          className="mt-1 w-full"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="create-region-country" className="text-label font-medium text-admin-fg">
          Landcode
        </label>
        <Input
          id="create-region-country"
          className="mt-1 w-full"
          placeholder="z. B. IT"
          maxLength={2}
          value={country}
          onChange={(e) => setCountry(e.target.value.toUpperCase())}
        />
        <p className="mt-1 text-caption text-admin-muted">
          Mittelpunkt und Fläche werden anhand von Name und Land ermittelt.
          Bei mehrdeutigen Namen (z. B. „Fehmarn") hilft der Landcode
          weiter — sonst zeigt der Fehler „Keine Koordinaten gefunden".
        </p>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>
          Abbrechen
        </Button>
        <Button type="submit" disabled={busy || !name.trim()}>
          {busy ? "Suche…" : "Anlegen"}
        </Button>
      </div>
      <DuplicateWarningDialog
        conflict={duplicateConflict}
        busy={busy}
        onClose={() => setDuplicateConflict(null)}
        onOverride={() => {
          setDuplicateConflict(null);
          void save(true);
        }}
      />
    </form>
  );
}
