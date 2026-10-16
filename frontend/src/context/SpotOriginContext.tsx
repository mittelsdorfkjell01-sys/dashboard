import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getSpotCatalogVersion } from "../lib/api";
import { ADMIN_DEPLOY } from "../lib/target";

/**
 * Whether the published catalogue currently holds **both** editorial and
 * community spots.
 *
 * The origin mark distinguishes authorship, not quality — and while every spot
 * is still ours it would sit on all of them and inform about nothing. So the
 * public surfaces ask this first and stay unmarked until the first community
 * spot is live; the flag comes from `/spots/version` (already a cheap, publicly
 * cached token endpoint), fetched once per session.
 */
/** Exported so a test (or a future surface that already knows the answer) can
 *  supply the flag without the fetch. */
export const SpotOriginContext = createContext(false);

export function SpotOriginProvider({ children }: { children: ReactNode }) {
  const [mixed, setMixed] = useState(false);

  useEffect(() => {
    // The admin deploy shows the origin as a plain field, never as the mark —
    // no reason to spend a request on the gate there.
    if (ADMIN_DEPLOY) return;
    let alive = true;
    getSpotCatalogVersion()
      .then((meta) => {
        if (alive) setMixed(Boolean(meta.origins_mixed));
      })
      // An unreachable catalogue is not a reason to invent an origin: stay on
      // the unmarked default.
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  return <SpotOriginContext.Provider value={mixed}>{children}</SpotOriginContext.Provider>;
}

/** True once the catalogue is mixed — i.e. once the origin mark means something. */
export function useSpotOriginsMixed(): boolean {
  return useContext(SpotOriginContext);
}
