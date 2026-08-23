/** Accessible two-handle range slider for the V3 wind-window selection.
 *  Two overlapping native `<input type="range">` elements — full keyboard,
 *  touch and screen-reader support come for free; no new UI dependency. */

export const WIND_WINDOW_MIN = 5;
export const WIND_WINDOW_MAX = 40; // slider position 40 always means "40+" (open upper bound)
const STEP = 1;

export function formatWindWindow(minWindKn: number, maxWindKn: number | null): string {
  return maxWindKn == null ? `${minWindKn}+ kt` : `${minWindKn}–${maxWindKn} kt`;
}

interface Props {
  minWindKn: number;
  maxWindKn: number | null; // null = open ("40+")
  onChange: (minWindKn: number, maxWindKn: number | null) => void;
  disabled?: boolean;
}

export default function WindWindowSlider({ minWindKn, maxWindKn, onChange, disabled }: Props) {
  const maxPos = maxWindKn ?? WIND_WINDOW_MAX;
  const lowPercent = ((minWindKn - WIND_WINDOW_MIN) / (WIND_WINDOW_MAX - WIND_WINDOW_MIN)) * 100;
  const highPercent = ((maxPos - WIND_WINDOW_MIN) / (WIND_WINDOW_MAX - WIND_WINDOW_MIN)) * 100;

  const setMin = (next: number) => {
    const clamped = Math.min(next, maxPos - 1);
    onChange(clamped, maxWindKn);
  };
  const setMax = (next: number) => {
    const clamped = Math.max(next, minWindKn + 1);
    onChange(minWindKn, clamped >= WIND_WINDOW_MAX ? null : clamped);
  };

  return (
    <div className="w-full">
      <div className="relative h-6">
        <div className="absolute left-0 right-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-line" />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-teal"
          style={{ left: `${lowPercent}%`, right: `${100 - highPercent}%` }}
        />
        <input
          type="range"
          className="v3-range-thumb absolute inset-x-0 top-1/2 w-full -translate-y-1/2 appearance-none bg-transparent"
          style={{ zIndex: minWindKn > WIND_WINDOW_MAX - 10 ? 5 : 3 }}
          min={WIND_WINDOW_MIN}
          max={WIND_WINDOW_MAX}
          step={STEP}
          value={minWindKn}
          disabled={disabled}
          aria-label="Mindestwindgeschwindigkeit"
          aria-valuetext={`${minWindKn} Knoten`}
          onChange={(e) => setMin(Number(e.target.value))}
        />
        <input
          type="range"
          className="v3-range-thumb absolute inset-x-0 top-1/2 w-full -translate-y-1/2 appearance-none bg-transparent"
          style={{ zIndex: 4 }}
          min={WIND_WINDOW_MIN}
          max={WIND_WINDOW_MAX}
          step={STEP}
          value={maxPos}
          disabled={disabled}
          aria-label="Höchstwindgeschwindigkeit"
          aria-valuetext={maxWindKn == null ? "40 Knoten oder mehr, offen" : `${maxWindKn} Knoten`}
          onChange={(e) => setMax(Number(e.target.value))}
        />
      </div>
      <div className="mt-1 flex justify-between text-data-caption text-muted">
        <span>{WIND_WINDOW_MIN} kt</span>
        <span>{WIND_WINDOW_MAX}+ kt</span>
      </div>
    </div>
  );
}
