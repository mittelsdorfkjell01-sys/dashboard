import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDownIcon } from "../lib/icons";
import { usePageBack } from "./PageBackLink";

/** Marks a page's own in-flow back control. Once that control has scrolled
 *  out above the viewport, the floating copy below takes over. */
export const PAGE_BACK_ATTR = "data-page-back";

/**
 * The back arrow that stays in the top-left corner while the visitor scrolls.
 *
 * Every page except the landing and the results page has a back control at its
 * top, but it scrolls away with the page — on a long spot Info/Daten page, a
 * region list or the help page, the only way back was scrolling all the way up
 * again or the browser gesture. This is the same step back, pinned.
 *
 * It appears only once the page's own back control (marked with
 * `data-page-back`) has left the viewport upwards, so the two are never on
 * screen together. Pages without one either pass `alwaysVisible` (short pages
 * whose top-left corner is otherwise empty) or fall back to a small scroll
 * threshold.
 *
 * The bare glyph (2026-11-21), like the maps' back control — it used to be a
 * white disc with the float shadow, which read as a big button on every page.
 * `onPhoto` sets it white for a page whose ground is a photograph.
 */
export default function ScrollBackButton({
  onBack,
  alwaysVisible = false,
  onPhoto = false,
}: {
  /** Defaults to the page back behaviour (history, or the landing page). */
  onBack?: () => void;
  alwaysVisible?: boolean;
  /** The page's ground is a photo: white glyph with a dark shadow. */
  onPhoto?: boolean;
}) {
  const { t } = useTranslation();
  const pageBack = usePageBack();
  const goBack = onBack ?? pageBack;
  const [visible, setVisible] = useState(alwaysVisible);

  useEffect(() => {
    if (alwaysVisible) {
      setVisible(true);
      return;
    }
    const target = document.querySelector<HTMLElement>(`[${PAGE_BACK_ATTR}]`);
    if (target && "IntersectionObserver" in window) {
      const observer = new IntersectionObserver(([entry]) =>
        setVisible(!entry.isIntersecting && entry.boundingClientRect.top < 0),
      );
      observer.observe(target);
      return () => observer.disconnect();
    }
    let frame = 0;
    const update = () => {
      frame = 0;
      setVisible(window.scrollY > 96);
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [alwaysVisible]);

  return (
    <button
      type="button"
      onClick={goBack}
      aria-label={t("common.back")}
      aria-hidden={!visible || undefined}
      tabIndex={visible ? undefined : -1}
      data-scroll-back
      className={`back-glyph ${onPhoto ? "back-glyph-on-photo" : ""} fixed left-2 top-[max(0.75rem,env(safe-area-inset-top))] z-header sm:left-4 ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
    >
      <ChevronDownIcon width={24} height={24} className="rotate-90" />
    </button>
  );
}
