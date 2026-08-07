import { heroManifest } from "../heroManifest";
import { hotlinkSrcSet, objectPosition } from "../lib/heroSource";

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
  delivery,
  provider,
}: {
  src: string;
  fallbackSrc?: string;
  alt: string;
  className?: string;
  focal?: { x: number; y: number } | null;
  /** How the bytes are served. `hotlinked` images stay on the provider's CDN
   *  (an Unsplash API condition) and are resized with its own parameters. */
  delivery?: "hotlinked" | "hosted";
  /** Provider slug — decides which CDN parameter dialect applies. */
  provider?: string | null;
}) {
  const entry = src.startsWith("/") ? heroManifest[keyFromSrc(src)] : undefined;
  const style = focal ? { objectPosition: objectPosition(focal) } : undefined;

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
        className={className}
        style={style}
        onError={onError}
      />
    );
  }

  if (!entry) {
    return <img src={src} alt={alt} className={className} style={style} onError={onError} />;
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
      <img src={entry.fallback} alt={alt} className={className} style={style} onError={onError} />
    </picture>
  );
}
