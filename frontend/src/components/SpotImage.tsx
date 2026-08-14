import { cardHotlinkSrcSet, unsplashSized } from "../lib/heroSource";

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
}: {
  src?: string;
  name: string;
  region?: string;
  className?: string;
  /** Smaller type for tight cards (map popup / strip). */
  compact?: boolean;
}) {
  if (src) {
    const srcSet = cardHotlinkSrcSet(src);
    return (
      <img
        src={srcSet ? unsplashSized(src, 640) : src}
        srcSet={srcSet}
        sizes={srcSet ? "(max-width: 639px) 50vw, (max-width: 1023px) 33vw, 20vw" : undefined}
        alt={name}
        loading="lazy"
        decoding="async"
        className={`h-full w-full object-cover ${className}`}
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
          compact ? "text-[13px]" : "text-[15px]"
        }`}
      >
        {name}
      </span>
      {region && (
        <span
          className={`leading-tight text-muted ${
            compact ? "text-[10px]" : "text-[11px]"
          }`}
        >
          {region}
        </span>
      )}
    </div>
  );
}
