// One glide at a time: a second tap on another day takes over from wherever
// the strip is at that moment.
let glideFrame = 0;

const GLIDE_MS = 450;
// MeteoChart's row-icon column (24px) plus the gap after it (4px).
const ICON_SLOT = 28;

/**
 * Scroll the Daten-page meteogram so a given local day sits at the strip's left
 * edge, then bring the whole meteogram into view. `date` is a
 * `local_date`/`date` string matching a `[data-forecast-day]` anchor rendered
 * by MeteoChart.
 *
 * The sideways move is our own 450 ms glide that brakes into the target
 * (chosen 2026-11-25, "Weiches Hinfahren zum Tag") instead of the browser's
 * smooth scroll, whose length and curve differ per browser. Touch snapping is
 * paused for the glide so it cannot tug the strip mid-way.
 */
export function scrollMeteogramToDay(date: string): void {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  requestAnimationFrame(() => {
    const scroller = document.getElementById("spot-meteogram-scroll");
    const dayAnchor = Array.from(scroller?.querySelectorAll<HTMLElement>("[data-forecast-day]") ?? [])
      .find((element) => element.dataset.forecastDay === date);
    if (scroller && dayAnchor) {
      // Past the first day the row icons are hidden, so the day lands at the
      // very left edge: skip the icon column's 24px + 4px gap as well.
      const left = dayAnchor.offsetLeft > 0 ? dayAnchor.offsetLeft + ICON_SLOT : 0;
      const target = Math.min(left, scroller.scrollWidth - scroller.clientWidth);
      if (reducedMotion) scroller.scrollLeft = target;
      else glideScrollLeft(scroller, target);
    }
    document.getElementById("spot-meteogramm")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  });
}

function glideScrollLeft(scroller: HTMLElement, target: number) {
  cancelAnimationFrame(glideFrame);
  const from = scroller.scrollLeft;
  if (Math.abs(target - from) < 1) {
    scroller.style.scrollSnapType = "";
    return;
  }
  scroller.style.scrollSnapType = "none";
  const start = performance.now();
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / GLIDE_MS);
    const eased = 1 - (1 - t) ** 3;
    scroller.scrollLeft = from + (target - from) * eased;
    if (t < 1) {
      glideFrame = requestAnimationFrame(step);
    } else {
      scroller.style.scrollSnapType = "";
    }
  };
  glideFrame = requestAnimationFrame(step);
}
