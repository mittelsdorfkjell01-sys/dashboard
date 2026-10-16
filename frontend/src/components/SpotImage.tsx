import { useEffect, useRef, useState } from "react";
import { cardHotlinkSrcSet, hostedSrcSet, objectPosition, unsplashSized } from "../lib/heroSource";

const CARD_LOAD_MARGIN = "100px 0px";

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
  eager = true,
}: {
  src?: string;
  name: string;
  region?: string;
  className?: string;
  width?: number | null;
  focal?: { x: number; y: number } | null;
  rotation?: number;
  /** Immediately fetch mounted browse cards; large expanded catalogues may opt out below the initial set. */
  eager?: boolean;
  /** Smaller type for tight cards (map popup / strip). */
  compact?: boolean;
}) {
  const placeholderRef = useRef<HTMLDivElement | null>(null);
  const [shouldLoad, setShouldLoad] = useState(eager);

  // Native loading="lazy" deliberately starts well before an image reaches the
  // viewport. That is useful for ordinary pages, but disastrous for this dense
  // catalogue when a legacy hero is several megabytes. Keep the image URL out
  // of the DOM until the card is genuinely close; the aspect-ratio wrapper in
  // SpotCard/RegionTile already reserves its space, so this does not add CLS.
  useEffect(() => {
    if (eager || shouldLoad || !src) return;
    const placeholder = placeholderRef.current;
    if (!placeholder || !("IntersectionObserver" in window)) {
      setShouldLoad(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setShouldLoad(true);
        observer.disconnect();
      },
      { rootMargin: CARD_LOAD_MARGIN },
    );
    observer.observe(placeholder);
    return () => observer.disconnect();
  }, [eager, shouldLoad, src]);

  if (src && !shouldLoad) {
    return (
      <div
        ref={placeholderRef}
        role="img"
        aria-label={name}
        data-deferred-spot-image
        className={`h-full w-full bg-band ${className}`}
      />
    );
  }

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
        loading={eager ? "eager" : "lazy"}
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
      className={`flex h-full w-full flex-col items-center justify-center gap-1 bg-gradient-to-br from-ink-soft to-muted px-3 text-center ${className}`}
    >
      <span
        className={`font-semibold leading-tight text-ink-soft ${
          compact ? "text-ui" : "text-body"
        }`}
      >
        {name}
      </span>
      {region && (
        <span
          className={`leading-tight text-muted ${
            compact ? "text-micro" : "text-caption"
          }`}
        >
          {region}
        </span>
      )}
    </div>
  );
}
