import { useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Spot description that starts collapsed and only offers a toggle when the
 * text is genuinely cut off, so a short description reads as a plain
 * paragraph.
 *
 * How much it shows depends on the column, not on a line count. From `lg` the
 * collapsed paragraph takes whatever height the Info column has left between
 * the spot header and the safety card below it (`flex-1` + `overflow-hidden`),
 * so the column ends flush with the gallery beside it at any text length.
 * Below `lg` there is no such column height to fill, so it falls back to a
 * three-line clamp.
 *
 * Clipping is measured, never counted: `scrollHeight > clientHeight` is true
 * for both the clamp and the flex-filled box, which is why one check covers
 * both modes and stays correct across widths, line heights and resizes.
 *
 * Motion (chosen 2026-11-24, "Klappt auf, Verlauf blendet"): the text box
 * eases from its old to its new height in 300ms and the fade over the last
 * line dissolves in 200ms, instead of the text jumping to full length.
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
  const boxRef = useRef<HTMLDivElement>(null);
  // Height of the text box just before a toggle, so the change can animate
  // from there (the browser cannot transition to or from `auto`).
  const fromHeight = useRef<number | null>(null);

  useLayoutEffect(() => {
    const box = boxRef.current;
    const from = fromHeight.current;
    fromHeight.current = null;
    if (!box || from == null) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const to = box.getBoundingClientRect().height;
    if (Math.abs(to - from) < 1) return;
    box.style.height = `${from}px`;
    box.style.overflow = "hidden";
    void box.offsetHeight; // commit the start height before transitioning
    box.style.transition = "height var(--sw-dur-slow) var(--sw-ease)";
    box.style.height = `${to}px`;
    const done = () => {
      box.style.height = "";
      box.style.overflow = "";
      box.style.transition = "";
    };
    const timer = window.setTimeout(done, 340);
    return () => {
      window.clearTimeout(timer);
      done();
    };
  }, [expanded]);

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
    <div
      className={`mt-5 sm:mt-8 ${
        expanded ? "" : "lg:flex lg:min-h-0 lg:flex-1 lg:flex-col"
      }`}
    >
      {/* Collapsed to three lines — enough to place the spot, short enough
          that the column stays calm. The last line fades into the page so the
          cut reads as "there is more" rather than as a hard crop; the fade is
          decorative and never covers the toggle. */}
      <div ref={boxRef} className={`relative ${expanded ? "" : "lg:min-h-0 lg:flex-1"}`}>
        <p
          ref={ref}
          className={`max-w-measure text-ui leading-relaxed text-ink-soft ${
            expanded ? "" : "line-clamp-3 lg:line-clamp-none lg:h-full lg:overflow-hidden"
          }`}
        >
          {text}
        </p>
        {(clipped || expanded) && (
          <div
            aria-hidden
            className={`pointer-events-none absolute inset-x-0 bottom-0 h-6 max-w-measure bg-gradient-to-t from-page/75 via-page/20 to-transparent transition-opacity duration-base motion-reduce:transition-none ${
              expanded ? "opacity-0" : "opacity-100"
            }`}
          />
        )}
      </div>
      {(clipped || expanded) && (
        <button
          type="button"
          onClick={() => {
            const next = !expanded;
            fromHeight.current = boxRef.current?.getBoundingClientRect().height ?? null;
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
