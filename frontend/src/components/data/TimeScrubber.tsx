import type { MouseEvent, PointerEvent } from "react";
import { useSpotDataScope } from "../../state/SpotDataScope";

export default function TimeScrubber() {
  const { selectedHour, setSelectedHour } = useSpotDataScope();
  const nowHour = new Date().getHours();

  const selectAt = (element: SVGSVGElement, clientX: number) => {
    const rect = element.getBoundingClientRect();
    setSelectedHour(((clientX - rect.left) / rect.width) * 24);
  };
  const handleClick = (event: MouseEvent<SVGSVGElement>) => selectAt(event.currentTarget, event.clientX);
  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (event.buttons === 1) selectAt(event.currentTarget, event.clientX);
  };
  const cursorX = (selectedHour / 24) * 500;
  const nowX = (nowHour / 24) * 500;

  return (
    <div className="flex items-center gap-3.5 border-t border-line-soft bg-surface px-4 py-2.5">
      <span className="shrink-0 text-caption font-medium uppercase tracking-wider text-muted">Heute</span>
      <div className="relative h-10 flex-1">
        <svg viewBox="0 0 500 40" preserveAspectRatio="none" className="h-full w-full cursor-ew-resize touch-none" onClick={handleClick} onPointerMove={handlePointerMove}>
          <rect x={0} y={12} width={nowX} height={14} fill="var(--sw-muted)" opacity={0.06} />
          <line x1={0} y1={20} x2={500} y2={20} stroke="var(--sw-line)" />
          {[0, 3, 6, 9, 12, 15, 18, 21, 24].map((hour) => <line key={hour} x1={(hour / 24) * 500} y1={14} x2={(hour / 24) * 500} y2={25} stroke="var(--sw-line)" strokeWidth={0.7} />)}
          {[0, 3, 6, 9, 12, 15, 18, 21].map((hour) => (
            <text key={hour} x={(hour / 24) * 500} y={38} textAnchor="middle" fontFamily="Poppins" fontSize={9} fill={hour === nowHour ? "var(--sw-orange)" : "var(--sw-muted)"} fontWeight={hour === nowHour ? 600 : 400} opacity={hour < nowHour && hour !== nowHour ? 0.4 : 1}>
              {hour === nowHour ? "jetzt" : String(hour).padStart(2, "0")}
            </text>
          ))}
          <text x={496} y={38} textAnchor="end" fontFamily="Poppins" fontSize={9} fill="var(--sw-muted)">24</text>
          <circle cx={cursorX} cy={20} r={7} fill="var(--sw-ink)" stroke="var(--sw-surface)" strokeWidth={1.5} />
          <text x={Math.max(24, Math.min(476, cursorX))} y={9} textAnchor="middle" fontFamily="Poppins" fontSize={9} fill="var(--sw-ink)" fontWeight={500}>{String(selectedHour).padStart(2, "0")}:00</text>
        </svg>
      </div>
    </div>
  );
}
