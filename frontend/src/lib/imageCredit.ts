// Attribution logic, shared by every place an image is shown.
//
// Credit is mandatory for every source, for different reasons: Unsplash and
// Pexels require it in their API terms, Wikimedia CC BY / BY-SA require it
// legally. Only public domain would be free — we show it anyway, because it
// costs nothing and an inconsistent credit line looks like an oversight.
//
// The admin never types any of this and cannot empty it; the server refuses an
// image object without a credit (see app/media/image_object.py).

import type { ImageRecord } from "./api";

/** Unsplash requires referral parameters on the links back to them. */
export const UNSPLASH_UTM = "utm_source=surfwinddata&utm_medium=referral";

/** Provider slug → the name shown to a reader. */
const PROVIDER_LABEL: Record<string, string> = {
  unsplash: "Unsplash",
  pexels: "Pexels",
  wikimedia: "Wikimedia Commons",
  openverse: "Openverse",
  upload: "surfwinddata",
  community: "Community",
  manual: "",
  seed: "",
  unknown: "",
};

/**
 * Providers whose "license" field holds one of our internal markers rather
 * than a public licence: an upload consent version ("v1") or "own". Printing
 * those next to a photographer's name would be noise, not attribution.
 */
const INTERNAL_LICENSE = /^(own|v\d+)$/i;

export interface CreditSource {
  credit?: string | null;
  creditUrl?: string | null;
  /** Machine slug (unsplash, wikimedia, community, …). */
  provider?: string | null;
  /** Display name as stored; falls back to the provider label. */
  source?: string | null;
  sourcePage?: string | null;
  license?: string | null;
  licenseUrl?: string | null;
}

export interface CreditPart {
  key: "photographer" | "provider" | "license";
  label: string;
  href?: string;
}

/**
 * Append Unsplash's referral parameters, once.
 *
 * The backend already adds them when it normalises a search result, so this
 * is idempotent — it exists for rows written before that and for links pasted
 * by hand.
 */
export function withUnsplashUtm(url: string | null | undefined, provider?: string | null): string | undefined {
  if (!url) return undefined;
  if (provider !== "unsplash") return url;
  if (url.includes("utm_source=")) return url;
  return `${url}${url.includes("?") ? "&" : "?"}${UNSPLASH_UTM}`;
}

/** Read an `image` object (spot/region hero) as a credit source. */
export function fromImageRecord(image?: ImageRecord | null): CreditSource | null {
  if (!image?.url) return null;
  return {
    credit: image.credit,
    creditUrl: image.credit_url,
    provider: image.provider,
    source: image.source,
    sourcePage: image.source_page,
    license: image.license,
    licenseUrl: image.license_url,
  };
}

/** Read a gallery row (community upload or Commons import) as a credit source. */
export function fromGalleryPhoto(photo: {
  credit?: string | null;
  source?: string | null;
  license_name?: string | null;
  license_url?: string | null;
  source_url?: string | null;
}): CreditSource {
  return {
    credit: photo.credit,
    provider: photo.source,
    source: photo.source,
    sourcePage: photo.source_url,
    license: photo.license_name,
    licenseUrl: photo.license_url,
  };
}

function providerLabel(source: CreditSource): string {
  const slug = (source.provider ?? "").toLowerCase();
  if (slug in PROVIDER_LABEL) return PROVIDER_LABEL[slug];
  // An unmapped slug is still better shown than swallowed — but our own
  // internal markers ("user_upload") should not surface as a brand name.
  if (slug === "user_upload" || slug === "wikimedia_commons") {
    return slug === "user_upload" ? "Community" : "Wikimedia Commons";
  }
  return source.source ?? "";
}

/**
 * The attribution, in reading order: who took it, where it came from, under
 * what licence. Parts with nothing to say are omitted rather than rendered
 * empty.
 */
export function creditParts(source: CreditSource | null): CreditPart[] {
  if (!source) return [];
  const parts: CreditPart[] = [];
  const provider = source.provider ?? undefined;

  const photographer = (source.credit ?? "").trim();
  if (photographer) {
    parts.push({
      key: "photographer",
      label: photographer,
      href: withUnsplashUtm(source.creditUrl, provider),
    });
  }

  const label = providerLabel(source).trim();
  if (label) {
    parts.push({
      key: "provider",
      label,
      href: withUnsplashUtm(source.sourcePage, provider),
    });
  }

  const license = (source.license ?? "").trim();
  if (license && !INTERNAL_LICENSE.test(license)) {
    parts.push({
      key: "license",
      label: license,
      href: source.licenseUrl ?? undefined,
    });
  }

  return parts;
}

/** Whether there is anything to render at all. */
export function hasCredit(source: CreditSource | null): boolean {
  return creditParts(source).length > 0;
}
