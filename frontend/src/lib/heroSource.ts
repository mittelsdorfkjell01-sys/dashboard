// How a hero image is actually fetched, decided by `delivery`.
//
// `hosted` — the bytes are in our own storage; the build-time manifest supplies
// AVIF/WebP variants where they exist.
// `hotlinked` — the bytes stay on the provider's CDN because their terms
// require it (Unsplash). Their CDN takes sizing parameters, so we can still
// serve a right-sized image without hosting anything.

/** Widths requested from a provider CDN, matching common hero display sizes. */
export const CDN_WIDTHS = [640, 1024, 1600, 2400, 3840] as const;

/** Smaller widths for browse cards. Even on a high-DPI desktop a card is
 * nowhere near hero size; keeping this list separate prevents a 3840 px source
 * from being selected for a roughly 300 px tile. */
export const CARD_CDN_WIDTHS = [320, 480, 640, 960] as const;

/** Unsplash CDN parameters: width, quality, format, and never upscale. */
export function unsplashSized(url: string, width: number): string {
  const [base, hash] = url.split("#");
  const separator = base.includes("?") ? "&" : "?";
  const sized = `${base}${separator}w=${width}&q=80&fm=jpg&fit=max`;
  return hash ? `${sized}#${hash}` : sized;
}

/**
 * A width-descriptor srcset for a hotlinked provider image.
 *
 * Returns undefined for anything we do not know how to resize — guessing at
 * another CDN's parameter names would produce broken URLs, and a plain <img>
 * is a perfectly good fallback.
 */
export function hotlinkSrcSet(url: string, provider?: string | null): string | undefined {
  if (provider !== "unsplash") return undefined;
  return CDN_WIDTHS.map((width) => `${unsplashSized(url, width)} ${width}w`).join(", ");
}

/** Responsive srcset for a spot/region card rather than a full-bleed hero. */
export function cardHotlinkSrcSet(url: string): string | undefined {
  try {
    if (new URL(url).hostname !== "images.unsplash.com") return undefined;
  } catch {
    return undefined;
  }
  return CARD_CDN_WIDTHS.map((width) => `${unsplashSized(url, width)} ${width}w`).join(", ");
}

/** Focal point → CSS object-position. Percentages, as stored. */
export function objectPosition(focal?: { x: number; y: number } | null): string | undefined {
  if (!focal) return undefined;
  return `${focal.x}% ${focal.y}%`;
}
