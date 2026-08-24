export default function MeteogramLegend() {
  const items = [
    { label: "Mittelwind", mark: <span className="h-4 w-3 rounded-[2px] bg-teal" /> },
    { label: "Böe", mark: <span className="relative h-4 w-3 rounded-[2px] border border-teal"><span className="absolute inset-x-0 top-0 h-1.5 bg-teal/30" /></span> },
    { label: "Modellspanne", mark: <span className="h-4 w-4 rounded-[2px] border border-ink-soft/40 bg-ink-soft/15" /> },
    { label: "Windrichtung", mark: <svg viewBox="0 0 18 18" className="h-4 w-4 text-ink-soft" aria-hidden><path d="M9 2v12m-4-4 4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg> },
    { label: "ausgewählter Zeitpunkt", mark: <span className="h-4 border-l-2 border-dashed border-orange" /> },
    { label: "keine Daten", mark: <span className="grid h-4 w-4 place-items-center text-muted">—</span> },
  ];
  return <div className="flex flex-wrap gap-x-5 gap-y-2 text-caption text-muted" aria-label="Zeichenerklärung">
    {items.map((item) => <span key={item.label} className="inline-flex items-center gap-2"><span aria-hidden className="inline-grid h-4 w-4 place-items-center">{item.mark}</span>{item.label}</span>)}
  </div>;
}
