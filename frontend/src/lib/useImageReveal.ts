import { useCallback, useEffect, useState } from "react";

type State = "pending" | "instant" | "loaded";

/**
 * Lets a photo arrive instead of popping in (chosen 2026-11-24, "Einblenden +
 * Setzen"): once its bytes are there it fades in over 250ms while settling
 * from 1.04 to 1 over 300ms (`.swd-img-reveal`, index.css). An image the
 * browser already has (cache, back navigation) is shown at once, unanimated —
 * a fade on every revisit would only slow the page down.
 *
 * Spread the result on the <img>: `<img {...reveal} … />`.
 */
export function useImageReveal(src: string | undefined) {
  const [state, setState] = useState<State>("pending");
  useEffect(() => setState("pending"), [src]);
  const ref = useCallback((img: HTMLImageElement | null) => {
    if (img?.complete && img.naturalWidth > 0) setState((current) => (current === "pending" ? "instant" : current));
  }, []);
  const onLoad = useCallback(() => setState((current) => (current === "pending" ? "loaded" : current)), []);
  return { ref, onLoad, "data-reveal": state } as const;
}
