// The attribution line. One component, several data sources.
//
// A stock hero, a Commons import and a community photo with an Instagram tag
// all render here, in the same place and the same style — the reader should
// not be able to tell which pipeline a photo came through, and we should not
// maintain three near-identical lines.

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
  if (parts.length === 0) return null;

  return (
    <span className={className}>
      {prefix}
      {parts.map((part, index) => (
        <span key={part.key}>
          {index > 0 && " · "}
          {part.href ? (
            <a
              href={part.href}
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-current/40 underline-offset-2 transition-colors hover:decoration-current"
            >
              {part.label}
            </a>
          ) : (
            part.label
          )}
        </span>
      ))}
    </span>
  );
}
