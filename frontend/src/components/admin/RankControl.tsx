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
    <div className="inline-flex items-center gap-2" role="group" aria-label="Rang">
      {/* Auto = white outline + white text (never a filled chip, so it stays
          readable on any background incl. dark). */}
      <button
        type="button"
        disabled={busy}
        onClick={() => onChange(null)}
        aria-pressed={value === null}
        title="Automatisch aus offenen Punkten"
        className={`h-7 rounded-md border px-2.5 text-caption font-medium transition-colors disabled:opacity-40 ${
          value === null
            ? "border-admin-fg text-admin-fg"
            : "border-admin-border text-admin-muted hover:border-admin-border-strong hover:text-admin-fg"
        }`}
      >
        Auto
      </button>
      <div className="flex items-center gap-1">
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
              className={`grid h-7 w-7 place-items-center rounded-md border transition-colors disabled:opacity-40 ${
                pinned
                  ? "border-admin-fg"
                  : autoHint
                    ? "border-dashed border-admin-border-strong"
                    : "border-transparent hover:border-admin-border"
              }`}
            >
              <span className={`h-3 w-3 rounded-full ${RANK_DOT[r]}`} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
