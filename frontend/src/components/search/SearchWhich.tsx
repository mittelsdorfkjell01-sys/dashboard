// "Welche?" panel — multi-select sport checkboxes (Frame_2) plus the disciplines
// (Freestyle / Big Air / Foil) below a fine divider (no heading). UI labels are
// the design's German words; sport values are backend keys (disciplines are
// forwarded as a param the backend does not read yet — see searchSubmit.ts).

const OPTIONS: { value: string; label: string }[] = [
  { value: "surf", label: "Surfen" },
  { value: "kitesurf", label: "Kitesurfen" },
  { value: "windsurf", label: "Windsurfen" },
  { value: "wing", label: "Wing" },
];

const DISCIPLINES: { value: string; label: string }[] = [
  { value: "freestyle", label: "Freestyle" },
  { value: "big_air", label: "Big Air" },
  { value: "foil", label: "Foil" },
];

function Row({
  label,
  checked,
  onToggle,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 transition-colors hover:bg-band">
      <span className="text-[15px] text-teal">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="h-5 w-5 shrink-0 accent-teal"
      />
    </label>
  );
}

export default function SearchWhich({
  value,
  onChange,
  disciplines,
  onDisciplinesChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  disciplines: string[];
  onDisciplinesChange: (next: string[]) => void;
}) {
  const toggle = (v: string) =>
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  const toggleDiscipline = (v: string) =>
    onDisciplinesChange(
      disciplines.includes(v)
        ? disciplines.filter((x) => x !== v)
        : [...disciplines, v]
    );

  return (
    <div className="flex flex-col">
      {OPTIONS.map((o) => (
        <Row
          key={o.value}
          label={o.label}
          checked={value.includes(o.value)}
          onToggle={() => toggle(o.value)}
        />
      ))}

      {/* fine divider, then the disciplines (no heading) */}
      <div className="my-2 h-px bg-line" />
      {DISCIPLINES.map((d) => (
        <Row
          key={d.value}
          label={d.label}
          checked={disciplines.includes(d.value)}
          onToggle={() => toggleDiscipline(d.value)}
        />
      ))}
    </div>
  );
}
