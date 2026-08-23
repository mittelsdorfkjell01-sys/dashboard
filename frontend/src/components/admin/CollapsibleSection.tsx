// A section wrapper that lets the operator collapse noisy blocks (Facilities,
// Gallery, Kommentare, Tide) while keeping the whole form structure intact.
//
// Default is expanded — a fresh page still shows everything — but each block's
// state persists per section id in localStorage, so an operator's preferred
// layout survives a reload without a server round-trip.
//
// Rendered as a native <section> so the outer page keeps its landmark
// semantics and the collapse header is a real <button> (screen readers,
// keyboard nav). The title lives inside the button; `aside` and `tone` slots
// mirror the props the existing sections already carry so wrapping an old
// block does not force a per-section restyle.

import { useEffect, useState, type ReactNode } from "react";

const STORAGE_PREFIX = "admin-collapsible:";

type Tone = "default" | "danger";

const TONE_CLASSES: Record<Tone, { border: string; bg: string; title: string }> = {
  default: {
    border: "border-admin-border",
    bg: "bg-admin-surface",
    title: "text-admin-fg",
  },
  danger: {
    border: "border-admin-danger-border",
    bg: "bg-admin-danger-bg",
    title: "text-admin-danger",
  },
};

function readStored(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  try {
    const v = window.localStorage.getItem(STORAGE_PREFIX + key);
    if (v === "0") return false;
    if (v === "1") return true;
  } catch {
    /* localStorage disabled — fall through to fallback */
  }
  return fallback;
}

export default function CollapsibleSection({
  id,
  title,
  aside,
  tone = "default",
  defaultOpen = true,
  mobileDefaultOpen,
  className = "",
  bodyClassName = "",
  children,
}: {
  /** DOM id — also the localStorage key and the anchor target for the burger
   *  menu's "jump to section" links. */
  id: string;
  title: ReactNode;
  /** Optional right-side content next to the heading (a button, a chip). */
  aside?: ReactNode;
  tone?: Tone;
  defaultOpen?: boolean;
  /** Separate first-visit default on touch layouts. Stored independently so
   collapsing a mobile form does not change the operator's desktop layout. */
  mobileDefaultOpen?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  const mobile =
    typeof window !== "undefined" &&
    window.matchMedia("(max-width: 1023px) and (pointer: coarse)").matches;
  const storageKey = `${id}:${mobile ? "mobile" : "desktop"}`;
  const [open, setOpen] = useState(() =>
    readStored(storageKey, mobile ? mobileDefaultOpen ?? defaultOpen : defaultOpen),
  );
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_PREFIX + storageKey, open ? "1" : "0");
    } catch {
      /* ignore storage failures */
    }
  }, [storageKey, open]);

  // The floating nav's "jump to section" dispatches this so a collapsed
  // block expands before the browser scrolls it into view — otherwise the
  // operator lands on a header they still have to click.
  useEffect(() => {
    const onOpen = (event: Event) => {
      const detail = (event as CustomEvent<{ id?: string }>).detail;
      if (detail?.id === id) setOpen(true);
    };
    window.addEventListener("collapsible:open", onOpen as EventListener);
    return () => window.removeEventListener("collapsible:open", onOpen as EventListener);
  }, [id]);

  const t = TONE_CLASSES[tone];
  const bodyId = `${id}-body`;

  return (
    <section
      id={id}
      className={`scroll-mt-24 rounded-lg border ${t.border} ${t.bg} p-4 sm:p-6 ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={bodyId}
          className="group -m-2 flex min-h-11 flex-1 items-center gap-2 rounded p-2 text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-admin-primary"
        >
          <svg
            viewBox="0 0 12 12"
            aria-hidden="true"
            className={`h-3 w-3 text-admin-muted transition-transform ${open ? "rotate-90" : ""}`}
          >
            <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <h2 className={`text-ui font-semibold ${t.title}`}>{title}</h2>
        </button>
        {aside && <div className="shrink-0">{aside}</div>}
      </div>
      {open && (
        <div id={bodyId} className={`mt-4 ${bodyClassName}`}>
          {children}
        </div>
      )}
    </section>
  );
}
