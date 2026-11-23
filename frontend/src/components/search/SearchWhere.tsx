// "Wohin?" panel: two compact columns of suggestions — Spots left, Regionen
// right. Presentational only: the filtered items, the keyboard-highlight index
// and the pick handler are owned by the search bar (so ↑/↓/Enter work).
//
// The rows are listbox options of the bar's combobox input: DOM focus stays in
// the input while ↑/↓ move `aria-activedescendant`, so the rows are taken out
// of the tab order (a mouse or tap still picks them).

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

type Column = "spot" | "region";

function Row({
  id,
  label,
  active,
  onClick,
}: {
  id: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      id={id}
      type="button"
      role="option"
      aria-selected={active}
      tabIndex={-1}
      onClick={onClick}
      className={`flex min-h-11 items-center rounded-card px-2 py-1.5 text-left transition-colors ${
        active ? "bg-band" : "hover:bg-band"
      }`}
    >
      {/* Two lines before clipping: a half-width column cut most longer
          spot names ("Fehmarn Wulfen…") at every desktop width. */}
      <span className="line-clamp-2 break-words text-body text-ink">{label}</span>
    </button>
  );
}

function ColumnList({
  id,
  title,
  empty,
  col,
  items,
  activeCol,
  activeRow,
  optionId,
  onPick,
}: {
  id: string;
  title: string;
  empty: string;
  col: Column;
  items: WhereItem[];
  activeCol: Column;
  activeRow: number;
  optionId: (col: Column, row: number) => string;
  onPick: (pick: WherePick) => void;
}) {
  const titleId = `${id}-title`;
  return (
    <div>
      <h3 id={titleId} className="mb-2 text-ui font-medium text-muted">{title}</h3>
      {items.length ? (
        <div id={id} role="listbox" aria-labelledby={titleId} className="flex flex-col gap-0.5">
          {items.map((it, i) => (
            <Row
              key={it.key}
              id={optionId(col, i)}
              label={it.label}
              active={activeCol === col && i === activeRow}
              onClick={() => onPick(it.pick)}
            />
          ))}
        </div>
      ) : (
        <p className="text-ui text-muted">{empty}</p>
      )}
    </div>
  );
}

export default function SearchWhere({
  listId,
  optionId,
  spotItems,
  regionItems,
  activeCol,
  activeRow,
  onPick,
}: {
  /** Id the combobox input points `aria-controls` at. */
  listId: string;
  /** Option id for a column/row — the input's `aria-activedescendant`. */
  optionId: (col: Column, row: number) => string;
  spotItems: WhereItem[];
  regionItems: WhereItem[];
  /** Which column the keyboard highlight is in, and the row within it (-1=none). */
  activeCol: Column;
  activeRow: number;
  onPick: (pick: WherePick) => void;
}) {
  return (
    <div id={listId} className="grid grid-cols-2 gap-x-6 gap-y-2">
      <ColumnList
        id={`${listId}-spots`}
        title="Spots"
        empty="Keine Spots gefunden."
        col="spot"
        items={spotItems}
        activeCol={activeCol}
        activeRow={activeRow}
        optionId={optionId}
        onPick={onPick}
      />
      <ColumnList
        id={`${listId}-regions`}
        title="Regionen"
        empty="Keine Regionen gefunden."
        col="region"
        items={regionItems}
        activeCol={activeCol}
        activeRow={activeRow}
        optionId={optionId}
        onPick={onPick}
      />
    </div>
  );
}
