import { useEffect, useRef, useState } from "react";

/**
 * Spot description that starts collapsed to a few lines at every viewport.
 * The toggle only appears when the text is actually clipped, so a short
 * description still reads as a plain paragraph.
 */
export default function SpotDescription({
  text,
  onExpandedChange,
}: {
  text: string;
  onExpandedChange?: (expanded: boolean) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [clipped, setClipped] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  // Only offer the toggle when the collapsed text is genuinely cut off. Measured
  // (not char-counted) so it stays correct across widths/line-heights, and
  // re-checked on resize (e.g. rotate, or crossing the sm breakpoint).
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setClipped(el.scrollHeight - el.clientHeight > 1);
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [text, expanded]);

  return (
    <div className="mt-5 sm:mt-8">
      {/* Collapsed to three lines — enough to place the spot, short enough
          that the column stays calm. The last line fades into the page so the
          cut reads as "there is more" rather than as a hard crop; the fade is
          decorative and never covers the toggle. */}
      <div className="relative">
        <p
          ref={ref}
          className={`max-w-measure text-ui leading-relaxed text-ink-soft ${
            expanded ? "" : "line-clamp-3"
          }`}
        >
          {text}
        </p>
        {!expanded && clipped && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-8 max-w-measure bg-gradient-to-t from-page to-transparent"
          />
        )}
      </div>
      {(clipped || expanded) && (
        <button
          type="button"
          onClick={() => {
            const next = !expanded;
            setExpanded(next);
            onExpandedChange?.(next);
          }}
          aria-expanded={expanded}
          className="mt-2 inline-flex min-h-11 items-center text-ui font-semibold text-ink underline underline-offset-4 transition-opacity hover:opacity-70"
        >
          {expanded ? "Weniger anzeigen" : "Mehr anzeigen"}
        </button>
      )}
    </div>
  );
}
