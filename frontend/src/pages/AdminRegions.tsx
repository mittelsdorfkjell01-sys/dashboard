// Admin regions (Sprint B): list with per-status spot counts, create a region,
// edit the model_pref default, and fetch a credited stock image.

import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  createRegion,
  getAdminRegions,
  setRegionStockImage,
  type AdminRegionEntry,
} from "../lib/api";
import { Button, Input } from "../components/ui";
import { PageHeader, Badge } from "../components/admin/ui";

export default function AdminRegions() {
  const [entries, setEntries] = useState<AdminRegionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await getAdminRegions());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 3000);
  };

  const onStockImage = async (id: string, name: string) => {
    setBusyId(id);
    setError(null);
    try {
      await setRegionStockImage(id);
      flash(`Stock-Bild für „${name}" gesetzt.`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Bild-Abruf fehlgeschlagen.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Regionen"
        description="Regionen anlegen, bearbeiten und ein Stock-Bild abrufen. Das Wettermodell wird automatisch nach den Koordinaten gewählt."
      />

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

      <CreateRegionForm
        onCreated={async (name) => {
          flash(`Region „${name}" angelegt.`);
          await load();
        }}
        onError={setError}
      />

      {/* Card list: single column, two columns on wide desktops (2xl) so the
          cards don't stretch into a huge empty middle. */}
      <div className="mt-8 grid grid-cols-1 gap-3 2xl:grid-cols-2">
        {loading ? (
          <div className="text-ui text-admin-muted">Lädt…</div>
        ) : entries.length === 0 ? (
          <div className="text-ui text-admin-muted">Noch keine Regionen.</div>
        ) : (
          entries.map((entry) => (
            <RegionCard
              key={entry.region.id}
              entry={entry}
              busy={busyId === entry.region.id}
              onStockImage={() => onStockImage(entry.region.id, entry.region.name)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function RegionCard({
  entry,
  busy,
  onStockImage,
}: {
  entry: AdminRegionEntry;
  busy: boolean;
  onStockImage: () => void;
}) {
  const { region, spot_counts } = entry;

  return (
    <div className="rounded-lg border border-admin-border bg-admin-surface p-4 transition-colors hover:border-admin-border-strong sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-admin-fg">
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
            className="rounded-md bg-admin-primary px-2.5 py-1 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover"
          >
            Bearbeiten
          </Link>
          <a
            href={`/region/${region.slug}`}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
          >
            Ansehen ↗
          </a>
          <button
            type="button"
            disabled={busy}
            onClick={onStockImage}
            className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
          >
            Stock-Bild
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateRegionForm({
  onCreated,
  onError,
}: {
  onCreated: (name: string) => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      // No coordinates: the backend geocodes the name → centre + bounds.
      await createRegion({
        name: name.trim(),
        country: country.trim() || undefined,
      });
      setName("");
      setCountry("");
      await onCreated(name.trim());
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="mt-6 rounded-lg border border-admin-border bg-admin-hover p-4 sm:p-5"
      noValidate
    >
      <p className="text-ui font-semibold text-admin-fg">Neue Region anlegen</p>
      <p className="mt-1 text-caption text-admin-muted">
        Nur Name (+ Land) — Mittelpunkt und Fläche werden automatisch aus dem
        Namen bestimmt.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Input
          className="min-w-[220px] flex-1"
          placeholder="Name (z. B. Sardinien)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Input
          className="w-40"
          placeholder="Land (z. B. IT)"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
        />
        <Button type="submit" disabled={busy || !name.trim()} className="shrink-0">
          {busy ? "Suche…" : "Anlegen"}
        </Button>
      </div>
    </form>
  );
}
