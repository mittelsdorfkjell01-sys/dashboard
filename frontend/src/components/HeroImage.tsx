import { useEffect, useState } from "react";
import { heroManifest } from "../heroManifest";
import { hotlinkSrcSet, objectPosition } from "../lib/heroSource";

/** Below this breakpoint the mobile focal (if set) applies. Matches Tailwind's
 *  `sm` — the same break at which the region hero switches to a portrait crop
 *  and the spot page collapses its columns. Kept in one place so the CSS
 *  breakpoint and the JS media query can't drift. */
const MOBILE_QUERY = "(max-width: 639.98px)";

function useMobileViewport(): boolean {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(MOBILE_QUERY).matches : false,
  );
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia(MOBILE_QUERY);
    const listener = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    mql.addEventListener("change", listener);
    setIsMobile(mql.matches);
    return () => mql.removeEventListener("change", listener);
  }, []);
  return isMobile;
}

const MIME: Record<string, string> = {
  avif: "image/avif",
  webp: "image/webp",
  jpg: "image/jpeg",
};

/** "/hero-welle.jpg" | "/hero-welle-1920.jpg" → "hero-welle" (manifest key). */
function keyFromSrc(src: string): string {
  const file = src.split("/").pop() ?? "";
  return file
    .replace(/\.(avif|webp|jpe?g|png)$/i, "")
    .replace(/-\d+$/, "");
}

/**
 * Full-bleed hero image. When the source has generated variants (see
 * scripts/gen_hero.py → heroManifest), it emits a <picture> with AVIF/WebP/JPEG
 * sources and a width-descriptor srcset + sizes="100vw", so the browser loads
 * the smallest file that still covers the display's CSS width × DPR — no
 * upscaling up to the largest generated width, and no oversized download on
 * mobile. Unknown/remote sources (e.g. picsum) render as a plain <img>.
 */
export default function HeroImage({
  src,
  fallbackSrc,
  alt,
  className,
  focal,
  focalMobile,
  rotation = 0,
  delivery,
  provider,
}: {
  src: string;
  fallbackSrc?: string;
  alt: string;
  className?: string;
  focal?: { x: number; y: number } | null;
  /** Applied only under the mobile breakpoint; when absent the desktop focal
   *  is used instead. A landscape photo often needs a different focal at 16:9
   *  mobile than at 21:9 desktop, hence the separate override. */
  focalMobile?: { x: number; y: number } | null;
  /** Subtle horizon correction; extra scale prevents exposed frame corners. */
  rotation?: number;
  /** How the bytes are served. `hotlinked` images stay on the provider's CDN
   *  (an Unsplash API condition) and are resized with its own parameters. */
  delivery?: "hotlinked" | "hosted";
  /** Provider slug — decides which CDN parameter dialect applies. */
  provider?: string | null;
}) {
  const isMobile = useMobileViewport();
  const activeFocal = isMobile && focalMobile ? focalMobile : focal;
  const entry = src.startsWith("/") ? heroManifest[keyFromSrc(src)] : undefined;
  const safeRotation = Math.max(-5, Math.min(5, rotation));
  const style = {
    ...(activeFocal ? { objectPosition: objectPosition(activeFocal) } : {}),
    transform: safeRotation
      ? `rotate(${safeRotation}deg) scale(${1 + Math.abs(safeRotation) * 0.04})`
      : undefined,
  };

  const onError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    if (fallbackSrc && e.currentTarget.src !== fallbackSrc) {
      e.currentTarget.src = fallbackSrc;
    }
  };

  // Hotlinked: no local variants exist, but the provider's CDN resizes for us,
  // so the browser still downloads a right-sized file instead of a 6000px original.
  const cdnSrcSet = delivery === "hotlinked" ? hotlinkSrcSet(src, provider) : undefined;
  if (cdnSrcSet) {
    return (
      <img
        src={src}
        srcSet={cdnSrcSet}
        sizes="100vw"
        alt={alt}
        loading="eager"
        fetchPriority="high"
        className={className}
        style={style}
        onError={onError}
      />
    );
  }

  if (!entry) {
    return <img src={src} alt={alt} loading="eager" fetchPriority="high" className={className} style={style} onError={onError} />;
  }

  const key = keyFromSrc(src);
  return (
    <picture>
      {entry.formats.map((fmt) => (
        <source
          key={fmt}
          type={MIME[fmt]}
          sizes="100vw"
          srcSet={entry.widths.map((w) => `/${key}-${w}.${fmt} ${w}w`).join(", ")}
        />
      ))}
      <img src={entry.fallback} alt={alt} loading="eager" fetchPriority="high" className={className} style={style} onError={onError} />
    </picture>
  );
}
