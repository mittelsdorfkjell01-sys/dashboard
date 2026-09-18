import { useEffect, useRef, useState } from "react";
import { ShareIcon, CheckCircleIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

/** Compact share toggle (no label), same chassis as the save button next to it.
 *  Uses the native share sheet on phones (`navigator.share`); where that isn't
 *  available (most desktops) it copies the link and briefly confirms. */
export default function ShareButton({ spot }: { spot: Spot }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number>();

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const onClick = async () => {
    const url = window.location.href;
    const shareData = { title: spot.name, text: `${spot.name} – ${spot.region}`, url };
    if (navigator.share) {
      try {
        await navigator.share(shareData);
        return;
      } catch {
        // User dismissed the sheet (AbortError) or share failed — fall through
        // to copy so the button still does something useful.
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked — nothing more we can do silently */
    }
  };

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Spot teilen"
      title={copied ? "Link kopiert" : "Spot teilen"}
      className="grid h-10 w-10 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      {copied ? (
        <CheckCircleIcon checkOnly width={18} height={18} className="text-green" />
      ) : (
        <ShareIcon className="text-sz-18" />
      )}
    </button>
  );
}
