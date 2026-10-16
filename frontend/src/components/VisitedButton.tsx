import { useState } from "react";
import { flushEvents, trackEvent } from "../lib/events";
import { AccountVisitedIcon } from "../lib/icons";

/**
 * "Spots besucht" — a compact round check-in that records a `session_checkin`
 * event for this spot (replaces the old inline "War heute hier" panel). Same
 * round icon chassis as the save/share buttons in the same row; the pin icon
 * matches the account menu's "Spots besucht" entry. Once tapped it settles into
 * an active (filled) state to confirm the visit.
 */
export default function VisitedButton({ spotId }: { spotId: string }) {
  const [visited, setVisited] = useState(false);

  const onClick = () => {
    if (visited) return;
    trackEvent("session_checkin", { spotId, surface: "spot" });
    void flushEvents();
    setVisited(true);
  };

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={visited}
      aria-label={visited ? "Als besucht markiert" : "Spots besucht"}
      title={visited ? "Als besucht markiert" : "Spots besucht"}
      className={`grid h-10 w-10 place-items-center rounded-full border transition-colors active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
        visited ? "border-ink bg-ink text-white" : "border-line text-ink hover:bg-band"
      }`}
    >
      <AccountVisitedIcon className="text-lead" />
    </button>
  );
}
