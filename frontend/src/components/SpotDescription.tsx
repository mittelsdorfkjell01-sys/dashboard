import { useEffect, useRef, useState } from "react";

/**
 * Spot description that starts collapsed to a few lines on mobile with a
 * "Mehr anzeigen" toggle; from `sm` up it shows in full (the description column
 * is wide there). The toggle only appears when the text is actually clipped, so
 * a short description still reads as a plain paragraph.
 */
export default function SpotDescription({ text }: { text: string }) {
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
      <p
        ref={ref}
        className={`max-w-[65ch] text-body leading-relaxed text-ink-soft ${
          expanded ? "" : "line-clamp-4 sm:line-clamp-none"
        }`}
      >
        {text}
      </p>
      {(clipped || expanded) && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 min-h-11 text-label font-semibold text-ink underline underline-offset-4 transition-opacity hover:opacity-70 sm:hidden"
        >
          {expanded ? "Weniger anzeigen" : "Mehr anzeigen"}
        </button>
      )}
    </div>
  );
}
