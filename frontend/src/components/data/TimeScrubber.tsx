import type { KeyboardEvent, MouseEvent, PointerEvent } from "react";
import { useSpotDataScope } from "../../state/SpotDataScope";

export default function TimeScrubber() {
  const { availableForecasts, selectedAtUtc, setSelectedAtUtc, selectedForecast } = useSpotDataScope();
  if (!availableForecasts.length) return null;

  const selectedIndex = Math.max(0, availableForecasts.findIndex((hour) => hour.utcKey === selectedAtUtc));
  const now = Date.now();
  const nowIndex = availableForecasts.reduce((best, hour, index) =>
    Math.abs(Date.parse(hour.utcKey) - now) < Math.abs(Date.parse(availableForecasts[best].utcKey) - now) ? index : best, 0);
  const denominator = Math.max(1, availableForecasts.length - 1);
  const cursorX = (selectedIndex / denominator) * 500;
  const nowX = (nowIndex / denominator) * 500;
  const tickStep = Math.max(1, Math.ceil(availableForecasts.length / 9));
  const ticks = availableForecasts.filter((_, index) => index % tickStep === 0 || index === availableForecasts.length - 1);

  const selectAt = (element: SVGSVGElement, clientX: number) => {
    const rect = element.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const index = Math.round(ratio * denominator);
    setSelectedAtUtc(availableForecasts[index]?.utcKey ?? null);
  };
  const handleClick = (event: MouseEvent<SVGSVGElement>) => selectAt(event.currentTarget, event.clientX);
  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (event.buttons === 1) selectAt(event.currentTarget, event.clientX);
  };
  const handleKeyDown=(event:KeyboardEvent<SVGSVGElement>)=>{
    const next=event.key==="Home"?0:event.key==="End"?denominator:event.key==="ArrowLeft"||event.key==="ArrowDown"?Math.max(0,selectedIndex-1):event.key==="ArrowRight"||event.key==="ArrowUp"?Math.min(denominator,selectedIndex+1):null;
    if(next==null)return;event.preventDefault();setSelectedAtUtc(availableForecasts[next].utcKey);
  };

  return (
    <div className="flex items-center gap-3.5 border-t border-line-soft bg-surface px-4 py-2.5">
      <span className="shrink-0 text-caption font-medium uppercase tracking-wider text-muted">Prognose</span>
      <div className="relative h-12 flex-1">
        <svg viewBox="0 0 500 48" preserveAspectRatio="none" tabIndex={0} className="h-full w-full cursor-ew-resize touch-none rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal" onClick={handleClick} onPointerMove={handlePointerMove} onKeyDown={handleKeyDown} role="slider" aria-label="Prognosezeitpunkt" aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={denominator} aria-valuenow={selectedIndex} aria-valuetext={selectedForecast ? `${selectedForecast.localDate} ${selectedForecast.localTimeWithOffset}` : "Keine Auswahl"}>
          <rect x={0} y={12} width={nowX} height={14} fill="var(--sw-muted)" opacity={0.06} />
          <line x1={0} y1={20} x2={500} y2={20} stroke="var(--sw-line)" />
          {ticks.map((hour) => { const index = availableForecasts.indexOf(hour); const x = (index / denominator) * 500; return <g key={hour.utcKey}><line x1={x} y1={14} x2={x} y2={25} stroke="var(--sw-line)" strokeWidth={1}/><text x={x} y={44} textAnchor={index === 0 ? "start" : index === denominator ? "end" : "middle"} fontFamily="Poppins" fontSize={12} fill={index === nowIndex ? "var(--sw-orange)" : "var(--sw-muted)"} fontWeight={index === nowIndex ? 600 : 400}>{index === nowIndex ? "jetzt" : hour.localTime}</text></g>; })}
          <circle cx={cursorX} cy={20} r={7} fill="var(--sw-ink)" stroke="var(--sw-surface)" strokeWidth={1.5} />
          <text x={Math.max(45, Math.min(455, cursorX))} y={10} textAnchor="middle" fontFamily="Poppins" fontSize={12} fill="var(--sw-ink)" fontWeight={600}>{selectedForecast?.localTimeWithOffset ?? "—"}</text>
        </svg>
      </div>
    </div>
  );
}
