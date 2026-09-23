import { Button, Field, Input, Select } from "../../components/ui";
import type { BoardType, GearKind, SportKey } from "../../lib/account";

export interface QuiverDraft {
  clientId: string;
  id?: string;
  sport: SportKey;
  kind: GearKind;
  size: number | null;
  boardType: BoardType | null;
  active: boolean;
  sortOrder: number;
}

const BOARD_LABELS: Record<BoardType, string> = {
  twintip: "Twintip",
  surfboard: "Surfboard",
  foil: "Foilboard",
  bigair_twintip: "Big-Air-Twintip",
};

function draftId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `draft-${Date.now()}-${Math.random()}`;
}

export default function QuiverEditor({
  items,
  onChange,
  disabled = false,
}: {
  items: QuiverDraft[];
  onChange: (items: QuiverDraft[]) => void;
  disabled?: boolean;
}) {
  const kites = items.filter((item) => item.kind === "kite");
  const board = items.find((item) => item.kind === "board" || item.kind === "foil");

  const updateKite = (clientId: string, size: number | null) => {
    onChange(items.map((item) => item.clientId === clientId ? { ...item, size } : item));
  };

  const removeKite = (clientId: string) => {
    onChange(items.filter((item) => item.clientId !== clientId));
  };

  const addKite = () => {
    onChange([...items, {
      clientId: draftId(), sport: "kitesurf", kind: "kite", size: null,
      boardType: null, active: true, sortOrder: kites.length,
    }]);
  };

  const setBoard = (boardType: BoardType | null) => {
    const withoutBoard = items.filter((item) => item.kind !== "board" && item.kind !== "foil");
    if (!boardType) {
      onChange(withoutBoard);
      return;
    }
    onChange([...withoutBoard, {
      clientId: board?.clientId ?? draftId(), id: board?.id,
      sport: "kitesurf", kind: "board", size: null, boardType,
      active: true, sortOrder: withoutBoard.length,
    }]);
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        {kites.map((kite, index) => (
          <div key={kite.clientId} className="flex items-end gap-3 border-b border-line pb-3 last:border-b-0">
            <div className="min-w-0 flex-1">
              <Field label={`Kite ${index + 1}`}>
                <div className="relative">
                  <Input
                  aria-label={`Größe Kite ${index + 1} in Quadratmetern`}
                  type="number"
                  min="1"
                  max="30"
                  step="0.5"
                  inputMode="decimal"
                  value={kite.size ?? ""}
                  disabled={disabled}
                  onChange={(event) => updateKite(
                    kite.clientId,
                    event.target.value === "" ? null : Number(event.target.value),
                  )}
                  className="pr-12"
                  />
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-label text-muted">m²</span>
                </div>
              </Field>
            </div>
            <Button
              variant="ghost"
              disabled={disabled}
              onClick={() => removeKite(kite.clientId)}
              aria-label={`Kite ${index + 1} entfernen`}
            >
              Entfernen
            </Button>
          </div>
        ))}
        {kites.length === 0 && (
          <p className="text-ui text-muted">Füge mindestens einen Kite hinzu.</p>
        )}
        <Button variant="secondary" disabled={disabled} onClick={addKite}>
          Kite hinzufügen
        </Button>
      </div>

      <Field label="Board-Typ" hint="Optional">
        <Select
          value={board?.boardType ?? ""}
          disabled={disabled}
          onChange={(event) => setBoard((event.target.value || null) as BoardType | null)}
        >
          <option value="">Nicht angegeben</option>
          {Object.entries(BOARD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </Select>
      </Field>
    </div>
  );
}
