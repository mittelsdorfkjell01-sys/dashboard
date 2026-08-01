import type { Rank } from "../../lib/api";
import { RANK_DOT, RANK_LABEL, RANKS } from "../../lib/rank";

/**
 * Compact traffic-light override picker used in the Fertigstellen list and the
 * editor's "Betrieb & Veröffentlichung" panel. "Auto" clears the override
 * (rank derived from readiness gaps); a colour pins it. When on Auto, the dot
 * the automatic value resolves to gets a dashed ring so it's still visible.
 */
export default function RankControl({
  value,
  effective,
  onChange,
  busy,
}: {
  /** The manual override, or null when following the automatic value. */
  value: Rank | null;
  /** The effective rank (override, else auto) — for the dashed hint on Auto. */
  effective: Rank;
  onChange: (rank: Rank | null) => void;
  busy?: boolean;
}) {
  return (
    <div className="inline-flex items-center gap-1" role="group" aria-label="Rang">
      <button
        type="button"
        disabled={busy}
        onClick={() => onChange(null)}
        aria-pressed={value === null}
        title="Automatisch aus offenen Punkten"
        className={`h-6 rounded-full px-2 text-caption font-medium transition disabled:opacity-40 ${
          value === null ? "bg-ink text-white" : "text-muted hover:bg-ink/5"
        }`}
      >
        Auto
      </button>
      {RANKS.map((r) => {
        const pinned = value === r;
        const autoHint = value === null && effective === r;
        return (
          <button
            key={r}
            type="button"
            disabled={busy}
            onClick={() => onChange(r)}
            aria-pressed={pinned}
            title={RANK_LABEL[r]}
            className={`grid h-6 w-6 place-items-center rounded-full transition hover:opacity-80 disabled:opacity-40 ${
              pinned ? "ring-2 ring-ink ring-offset-1" : autoHint ? "ring-1 ring-ink/30 ring-offset-1" : ""
            }`}
          >
            <span className={`h-3 w-3 rounded-full ${RANK_DOT[r]}`} />
          </button>
        );
      })}
    </div>
  );
}
