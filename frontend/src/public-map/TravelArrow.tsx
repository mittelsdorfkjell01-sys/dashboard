/**
 * The map's one arrow drawn as an icon: the same form as the canvas lattice
 * (ArrowLayer.ts) — a shaft and a filled head of ~35 % — pointing where the
 * wind or the waves GO. `bearing` is that travel bearing (0 = north).
 * Below the calm threshold the caller draws `CalmMark` instead.
 */
export function TravelArrow({ bearing, color = "currentColor", size = 14, className = "" }: { bearing: number; color?: string; size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className={`shrink-0 ${className}`} style={{ transform: `rotate(${Math.round(bearing)}deg)` }}>
      <path d="M12 21.5V9.5" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
      <path d="M12 2.5l5.4 8.4H6.6z" fill={color} />
    </svg>
  );
}

export function CalmMark({ size = 14, className = "" }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className={`shrink-0 ${className}`}>
      <circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" strokeWidth="2.2" />
    </svg>
  );
}
