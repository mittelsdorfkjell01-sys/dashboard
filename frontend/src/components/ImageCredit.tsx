// The attribution line. One component, several data sources.
//
// A stock hero, a Commons import and a community photo with an Instagram tag
// all render here, in the same place and the same style — the reader should
// not be able to tell which pipeline a photo came through, and we should not
// maintain three near-identical lines.
//
// Visible line is only the photographer. A small "i" button opens a popover
// with source and licence — keeping the hero visually quiet while satisfying
// the attribution obligation for CC BY / BY-SA and the Unsplash / Pexels API
// terms.

import { useEffect, useId, useRef, useState } from "react";
import { creditParts, type CreditSource } from "../lib/imageCredit";

function InfoIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 7.5v3.25" strokeLinecap="round" />
      <circle cx="8" cy="5.25" r="0.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

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
  const provider = parts.find((p) => p.key === "provider");
  const license = parts.find((p) => p.key === "license");
  const hasDetails = Boolean(provider || license);

  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const popoverId = useId();

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (parts.length === 0) return null;

  // If nothing beyond a photographer name is present, we render the plain line
  // — the info button would open an empty popover, which is worse than nothing.
  if (!photographer && !hasDetails) return null;

  return (
    <span ref={wrapRef} className={`relative inline-flex items-center gap-1.5 ${className}`}>
      <span>
        {prefix}
        {photographer ? (
          photographer.href ? (
            <a
              href={photographer.href}
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-current/40 underline-offset-2 transition-colors hover:decoration-current"
            >
              {photographer.label}
            </a>
          ) : (
            photographer.label
          )
        ) : (
          <span className="italic text-current/70">unbekannt</span>
        )}
      </span>
      {hasDetails && (
        <>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Bildquelle schließen" : "Bildquelle anzeigen"}
            aria-expanded={open}
            aria-controls={popoverId}
            className="grid h-4 w-4 place-items-center rounded-full text-current/70 transition-colors hover:text-current focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-current"
          >
            <InfoIcon />
          </button>
          {open && (
            <span
              id={popoverId}
              role="dialog"
              aria-label="Bildquelle"
              className="pointer-events-auto absolute bottom-full right-0 z-20 mb-2 w-max max-w-[260px] rounded-md border border-white/15 bg-ink/95 px-3 py-2 text-left text-caption text-white shadow-lg"
            >
              {provider && (
                <span className="block">
                  Quelle:{" "}
                  {provider.href ? (
                    <a
                      href={provider.href}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="underline decoration-white/50 underline-offset-2 hover:decoration-white"
                    >
                      {provider.label}
                    </a>
                  ) : (
                    provider.label
                  )}
                </span>
              )}
              {license && (
                <span className="mt-1 block">
                  Lizenz:{" "}
                  {license.href ? (
                    <a
                      href={license.href}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="underline decoration-white/50 underline-offset-2 hover:decoration-white"
                    >
                      {license.label}
                    </a>
                  ) : (
                    license.label
                  )}
                </span>
              )}
            </span>
          )}
        </>
      )}
    </span>
  );
}
