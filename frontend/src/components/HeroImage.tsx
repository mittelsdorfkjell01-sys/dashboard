import { useEffect, useState } from "react";
import { heroManifest } from "../heroManifest";
import { hostedSrcSet, hotlinkSrcSet, objectPosition } from "../lib/heroSource";

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

/** React 18 does not expose the standards-based lowercase attribute in its
 * JSX typings. A spread keeps the emitted DOM attribute correct and avoids the
 * development warning from React's legacy camel-cased prop path. */
function fetchPriorityAttribute(priority: boolean) {
  return { fetchpriority: priority ? "high" : "low" } as {
    fetchpriority: "high" | "low";
  };
}

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
  width,
  delivery,
  provider,
  priority = true,
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
  /** Stored pixel width, used to describe generated hosted variants. */
  width?: number | null;
  /** How the bytes are served. `hotlinked` images stay on the provider's CDN
   *  (an Unsplash API condition) and are resized with its own parameters. */
  delivery?: "hotlinked" | "hosted";
  /** Provider slug — decides which CDN parameter dialect applies. */
  provider?: string | null;
  /** Reserve high network priority for the one image that can become LCP. */
  priority?: boolean;
}) {
  const isMobile = useMobileViewport();
  const [imageAttempt, setImageAttempt] = useState<"primary" | "fallback" | "failed">("primary");
  useEffect(() => setImageAttempt("primary"), [src, fallbackSrc]);
  const useFallback = imageAttempt === "fallback" && Boolean(fallbackSrc);
  const displayedSrc = useFallback ? fallbackSrc! : src;
  const activeFocal = isMobile && focalMobile ? focalMobile : focal;
  const entry = !useFallback && src.startsWith("/") ? heroManifest[keyFromSrc(src)] : undefined;
  const safeRotation = Math.max(-5, Math.min(5, rotation));
  const style = {
    ...(activeFocal ? { objectPosition: objectPosition(activeFocal) } : {}),
    transform: safeRotation
      ? `rotate(${safeRotation}deg) scale(${1 + Math.abs(safeRotation) * 0.04})`
      : undefined,
  };

  const onError = () => {
    setImageAttempt((current) =>
      current === "primary" && fallbackSrc && fallbackSrc !== src ? "fallback" : "failed"
    );
  };

  if (imageAttempt === "failed") {
    return (
      <div
        role="img"
        aria-label={alt || "Bild nicht verfügbar"}
        className={`${className ?? ""} grid place-items-center bg-ink px-4 text-center text-caption text-white/80`}
      >
        Bild nicht verfügbar
      </div>
    );
  }

  // Hotlinked: no local variants exist, but the provider's CDN resizes for us,
  // so the browser still downloads a right-sized file instead of a 6000px original.
  const cdnSrcSet = !useFallback && delivery === "hotlinked" ? hotlinkSrcSet(src, provider) : undefined;
  const storedSrcSet = !useFallback && delivery !== "hotlinked" ? hostedSrcSet(src, width) : undefined;
  const dynamicSrcSet = cdnSrcSet ?? storedSrcSet;
  if (dynamicSrcSet) {
    return (
      <img
        src={displayedSrc}
        srcSet={dynamicSrcSet}
        sizes="100vw"
        alt={alt}
        loading={priority ? "eager" : "lazy"}
        {...fetchPriorityAttribute(priority)}
        decoding="async"
        className={className}
        style={style}
        onError={onError}
      />
    );
  }

  if (!entry) {
    return <img src={displayedSrc} alt={alt} loading={priority ? "eager" : "lazy"} {...fetchPriorityAttribute(priority)} decoding="async" className={className} style={style} onError={onError} />;
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
      <img src={entry.fallback} alt={alt} loading={priority ? "eager" : "lazy"} {...fetchPriorityAttribute(priority)} decoding="async" className={className} style={style} onError={onError} />
    </picture>
  );
}
