import { cardHotlinkSrcSet, hostedSrcSet, objectPosition, unsplashSized } from "../lib/heroSource";

/**
 * A spot's image with a branded fallback. When `src` is empty (a seed spot with
 * no hero uploaded yet), it renders a calm brand-coloured field carrying the
 * spot name + region instead of an external placeholder — so the grid never
 * shows a broken image or a random `picsum` photo.
 */
export default function SpotImage({
  src,
  name,
  region,
  className = "",
  compact = false,
  width,
  focal,
  rotation = 0,
}: {
  src?: string;
  name: string;
  region?: string;
  className?: string;
  width?: number | null;
  focal?: { x: number; y: number } | null;
  rotation?: number;
  /** Smaller type for tight cards (map popup / strip). */
  compact?: boolean;
}) {
  if (src) {
    const hotlinked = cardHotlinkSrcSet(src);
    const srcSet = hotlinked ?? hostedSrcSet(src, width);
    const safeRotation = Math.max(-5, Math.min(5, rotation));
    return (
      <img
        src={hotlinked ? unsplashSized(src, 640) : src}
        srcSet={srcSet}
        sizes={srcSet ? "(max-width: 639px) 50vw, (max-width: 1023px) 33vw, 20vw" : undefined}
        alt={name}
        loading="lazy"
        decoding="async"
        className={`h-full w-full object-cover ${className}`}
        style={{
          objectPosition: objectPosition(focal),
          transform: safeRotation
            ? `rotate(${safeRotation}deg) scale(${1 + Math.abs(safeRotation) * 0.04})`
            : undefined,
        }}
      />
    );
  }
  return (
    <div
      role="img"
      aria-label={region ? `${name}, ${region}` : name}
      className={`flex h-full w-full flex-col items-center justify-center gap-1 bg-gradient-to-br from-ink-soft to-[#c2d3e6] px-3 text-center ${className}`}
    >
      <span
        className={`font-semibold leading-tight text-ink-soft ${
          compact ? "text-label" : "text-body"
        }`}
      >
        {name}
      </span>
      {region && (
        <span
          className={`leading-tight text-muted ${
            compact ? "text-sz-10" : "text-sz-11"
          }`}
        >
          {region}
        </span>
      )}
    </div>
  );
}
