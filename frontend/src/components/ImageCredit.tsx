// The attribution line. One component, several data sources.
//
// A stock hero, a Commons import and a community photo with an Instagram tag
// all render here, in the same place and the same style — the reader should
// not be able to tell which pipeline a photo came through, and we should not
// maintain three near-identical lines.
//
// Renders only the photographer and the licence — provider names live in the
// admin picker's LicenseCard. That satisfies the CC BY / BY-SA obligation and
// the Unsplash / Pexels API terms (photographer must be named and linked)
// without cluttering the hero with a provider brand.

import { creditParts, type CreditSource } from "../lib/imageCredit";

export default function ImageCredit({
  source,
  className = "",
  prefix = "Foto: ",
}: {
  source: CreditSource | null;
  /** Positioning is the caller's business; the inner styling is not. */
  className?: string;
  prefix?: string;
}) {
  const parts = creditParts(source);
  const photographer = parts.find((p) => p.key === "photographer");
  const license = parts.find((p) => p.key === "license");
  if (!photographer && !license) return null;

  const linkClass =
    "underline decoration-current/40 underline-offset-2 transition-colors hover:decoration-current";

  return (
    <span className={className}>
      {prefix}
      {photographer ? (
        photographer.href ? (
          <a href={photographer.href} target="_blank" rel="noreferrer noopener" className={linkClass}>
            {photographer.label}
          </a>
        ) : (
          photographer.label
        )
      ) : (
        <span className="italic text-current/70">unbekannt</span>
      )}
      {license && (
        <>
          {" · "}
          {license.href ? (
            <a href={license.href} target="_blank" rel="noreferrer noopener" className={linkClass}>
              {license.label}
            </a>
          ) : (
            license.label
          )}
        </>
      )}
    </span>
  );
}
