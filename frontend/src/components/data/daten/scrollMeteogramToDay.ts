/**
 * Scroll the Daten-page meteogram so a given local day sits at the strip's left
 * edge, then bring the whole meteogram into view. Shared by the day-overview
 * strip above the meteogram and the 10-day outlook grid below it, so both jump
 * the same way. `date` is a `local_date`/`date` string matching a
 * `[data-forecast-day]` anchor rendered by MeteoChart.
 */
export function scrollMeteogramToDay(date: string): void {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const behavior: ScrollBehavior = reducedMotion ? "auto" : "smooth";

  requestAnimationFrame(() => {
    const scroller = document.getElementById("spot-meteogram-scroll");
    const dayAnchor = Array.from(scroller?.querySelectorAll<HTMLElement>("[data-forecast-day]") ?? [])
      .find((element) => element.dataset.forecastDay === date);
    if (scroller && dayAnchor) {
      scroller.scrollTo({ left: dayAnchor.offsetLeft, top: 0, behavior });
    }
    document.getElementById("spot-meteogramm")?.scrollIntoView({ behavior, block: "start" });
  });
}
