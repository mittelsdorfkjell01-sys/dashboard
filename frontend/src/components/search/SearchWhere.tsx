// "Wohin?" panel: two compact columns of suggestions — Spots left, Regionen
// right. Presentational only: the filtered items, the keyboard-highlight index
// and the pick handler are owned by the search bar (so ↑/↓/Enter work).

import type { WhereSelection } from "../../lib/searchSubmit";

export interface WherePick extends WhereSelection {
  country?: string | null;
}

/** A rendered suggestion: a stable key, its label, and the pick it commits. */
export interface WhereItem {
  key: string;
  label: string;
  pick: WherePick;
}

function Row({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center rounded-lg px-2 py-1.5 text-left transition-colors ${
        active ? "bg-band" : "hover:bg-band"
      }`}
    >
      <span className="truncate text-[15px] text-ink">{label}</span>
    </button>
  );
}

export default function SearchWhere({
  spotItems,
  regionItems,
  activeCol,
  activeRow,
  onPick,
}: {
  spotItems: WhereItem[];
  regionItems: WhereItem[];
  /** Which column the keyboard highlight is in, and the row within it (-1=none). */
  activeCol: "spot" | "region";
  activeRow: number;
  onPick: (pick: WherePick) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-2">
      {/* Spots left */}
      <div>
        <h3 className="mb-2 text-[13px] font-medium text-muted">Spots</h3>
        {spotItems.length ? (
          <div className="flex flex-col gap-0.5">
            {spotItems.map((it, i) => (
              <Row
                key={it.key}
                label={it.label}
                active={activeCol === "spot" && i === activeRow}
                onClick={() => onPick(it.pick)}
              />
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-muted">Keine Spots gefunden.</p>
        )}
      </div>

      {/* Regionen right */}
      <div>
        <h3 className="mb-2 text-[13px] font-medium text-muted">Regionen</h3>
        {regionItems.length ? (
          <div className="flex flex-col gap-0.5">
            {regionItems.map((it, i) => (
              <Row
                key={it.key}
                label={it.label}
                active={activeCol === "region" && i === activeRow}
                onClick={() => onPick(it.pick)}
              />
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-muted">Keine Regionen gefunden.</p>
        )}
      </div>
    </div>
  );
}
