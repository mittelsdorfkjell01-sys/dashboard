/**
 * An "at a glance" facts list. `variant="row"` (default) is the inline
 * definition list, ruled top and bottom — the editorial alternative to a grid
 * of little cards. `variant="rail"` is stacked "data blocks" (label small and
 * teal above a bold value) for the Steckbrief module next to Facilities —
 * two columns from `sm`, one hairline above the whole block instead of a rule
 * per row. Renders nothing when there are no facts.
 */
export default function FactRow({
  items,
  variant = "row",
}: {
  items: { label: string; value: string }[];
  variant?: "row" | "rail";
}) {
  if (items.length === 0) return null;

  if (variant === "rail") {
    return (
      <div>
        <p className="text-caption font-medium uppercase tracking-[0.18em] text-teal">
          Steckbrief
        </p>
        <dl className="mt-4 grid grid-cols-1 gap-x-10 gap-y-7 border-t border-line pt-6 sm:grid-cols-2">
          {items.map((f) => (
            <div key={f.label}>
              <dt className="text-caption font-medium uppercase tracking-[0.18em] text-teal">
                {f.label}
              </dt>
              <dd className="mt-1.5 text-title font-semibold text-ink">{f.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    );
  }

  return (
    <dl className="flex flex-wrap items-baseline gap-x-12 gap-y-4 border-y border-line py-6">
      {items.map((f) => (
        <div key={f.label} className="flex flex-col">
          <dt className="text-caption text-muted">{f.label}</dt>
          <dd className="mt-1 text-body font-medium text-ink">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}
