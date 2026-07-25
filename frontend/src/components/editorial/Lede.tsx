import type { ReactNode } from "react";

/**
 * The editorial lede — a wide, comfortable reading column for the spot/region
 * write-up. Capped at ~68ch, larger type, relaxed leading (baked into the
 * `text-lede` token). Falls back to a quiet placeholder when there is no copy.
 */
export default function Lede({ children }: { children?: ReactNode }) {
  return (
    <div className="max-w-[68ch] text-lede text-ink-soft text-pretty">
      {children ? (
        children
      ) : (
        <span className="text-muted">Noch keine Beschreibung hinterlegt.</span>
      )}
    </div>
  );
}
