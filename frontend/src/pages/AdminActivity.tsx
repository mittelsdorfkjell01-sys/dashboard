// Team activity log — its own back-office page (moved out of Benutzer). Shows
// the latest team changes, one summarized entry per spot, searchable. Clicking a
// spot entry opens a read-only change preview.

import { useEffect, useState } from "react";
import { getActivity, type ActivityItem } from "../lib/api";
import { gapLabel } from "../lib/labels";
import ActivityPreview from "../components/admin/ActivityPreview";
import { PageHeader, SearchInput } from "../components/admin/ui";

export default function AdminActivity() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [q, setQ] = useState("");
  const [preview, setPreview] = useState<ActivityItem | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      getActivity(q.trim() || undefined)
        .then(setItems)
        .catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div>
      <PageHeader
        title="Aktivität"
        actions={
          <SearchInput
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Name oder Spot suchen …"
            className="w-full sm:max-w-[260px]"
          />
        }
      />

      <ul className="divide-y divide-admin-border-subtle rounded-lg border border-admin-border bg-admin-surface">
        {items.length === 0 ? (
          <li className="px-4 py-6 text-center text-label text-admin-muted">
            Noch keine Aktivität.
          </li>
        ) : (
          items.map((a, i) => {
            const clickable = a.kind === "spot" && !!a.target_id;
            const content = (
              <>
                <span className="min-w-0 text-ink">
                  <span className="font-medium">{a.actor ?? "—"}</span>{" "}
                  <span className="text-muted">{a.label}</span>
                  {a.target && <span className="text-ink"> — {a.target}</span>}
                  {a.fields.length > 0 && (
                    <span className="text-muted"> ({a.fields.map(gapLabel).join(", ")})</span>
                  )}
                  {a.actions && a.actions > 1 && (
                    <span className="text-caption text-muted"> · {a.actions} Änderungen</span>
                  )}
                </span>
                <span className="admin-mono shrink-0 text-caption text-admin-muted">
                  {a.at ? new Date(a.at).toLocaleString("de-DE") : ""}
                </span>
              </>
            );
            return (
              <li key={i}>
                {clickable ? (
                  <button
                    type="button"
                    onClick={() => setPreview(a)}
                    className="flex w-full items-start justify-between gap-3 px-4 py-2.5 text-left text-ui transition-colors hover:bg-admin-hover"
                  >
                    {content}
                  </button>
                ) : (
                  <div className="flex items-start justify-between gap-3 px-4 py-2.5 text-ui">
                    {content}
                  </div>
                )}
              </li>
            );
          })
        )}
      </ul>

      <ActivityPreview item={preview} onClose={() => setPreview(null)} />
    </div>
  );
}
