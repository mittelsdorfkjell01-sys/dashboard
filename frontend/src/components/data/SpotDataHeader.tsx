import type { Spot } from "../../lib/types";
import { useSpotDataScope } from "../../state/SpotDataScope";

export default function SpotDataHeader({ spot }: { spot: Spot }) {
  const { sportMode, setSportMode, windUnit, setWindUnit } = useSpotDataScope();
  const region = spot.region.split(",")[0]?.trim() || spot.region;

  return (
    <div className="grid gap-3 py-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
      <div className="flex min-w-0 flex-wrap items-baseline gap-2.5">
        <h1 className="text-title font-semibold tracking-tight text-ink">{spot.name}</h1>
        <span className="text-body font-light text-muted">{region}</span>
      </div>
      <Toggle
        value={sportMode}
        onChange={setSportMode}
        options={[{ id: "wind", label: "Wind" }, { id: "surf", label: "Surf" }]}
        label="Sportmodus"
      />
      <div className="sm:justify-self-end">
        <Toggle
          compact
          value={windUnit}
          onChange={setWindUnit}
          options={[{ id: "kts", label: "kts" }, { id: "ms", label: "m/s" }]}
          label="Windeinheit"
        />
      </div>
    </div>
  );
}

function Toggle<T extends string>({ value, onChange, options, label, compact = false }: {
  value: T;
  onChange: (value: T) => void;
  options: Array<{ id: T; label: string }>;
  label: string;
  compact?: boolean;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex w-fit rounded-full border border-line bg-band p-0.5">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={value === option.id}
          onClick={() => onChange(option.id)}
          className={`${compact ? "px-2 py-0.5 text-[10px]" : "px-3.5 py-1 text-caption"} rounded-full font-medium tracking-wide transition-colors ${
            value === option.id ? "bg-teal text-white" : "text-muted hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
