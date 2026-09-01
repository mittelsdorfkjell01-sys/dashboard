import type { Facility, FacilityKind } from "../lib/types";
import { ParkingIcon, SchoolIcon, ShowerIcon, FoodIcon, CampingIcon } from "../lib/icons";

const facilityIcon: Record<FacilityKind, (p: { width?: number; height?: number; className?: string }) => JSX.Element> = {
  parking: ParkingIcon,
  school: SchoolIcon,
  shower: ShowerIcon,
  food: FoodIcon,
  camping: CampingIcon,
};

/** "Facilities" panel — icon + title + one-line note per amenity. Headless:
 *  the section heading lives in the caller's `SectionBand`. All five kinds
 *  always render (never hidden), in three visually distinct states, because
 *  "not present" and "nobody checked" are different claims and the page must
 *  never conflate them:
 *   - available: true  → icon full, normal title/note
 *   - available: false → icon muted + title struck through (demonstrably absent)
 *   - available: null  → icon at 30% opacity, no strikethrough, "Keine Angabe"
 *
 *  `variant="grid"` (default) is the icon-tile grid; `variant="rail"` is the
 *  hairline-table look for the sticky spec rail next to the lede; `variant="list"`
 *  is the calm, divider-free facts list for the Info page's narrow side column.
 */
export default function Facilities({
  items,
  variant = "grid",
}: {
  items: Facility[];
  variant?: "grid" | "rail" | "list" | "icons";
}) {
  if (items.length === 0) return null;

  if (variant === "icons") {
    return (
      <div className="flex flex-wrap items-start gap-x-5 gap-y-3">
        {items.map((f) => {
          const Icon = facilityIcon[f.kind];
          const absent = f.available === false;
          const unknown = f.available === null;
          return (
            <div key={f.kind} className="flex flex-col items-center gap-1.5">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-[14px] bg-band ${
                  absent ? "opacity-40" : unknown ? "opacity-30" : ""
                }`}
              >
                <Icon width={16} height={16} className="text-ink-soft" />
              </div>
              <span className={`text-caption tracking-wide ${absent ? "text-muted line-through" : "text-muted"}`}>
                {f.title}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  if (variant === "list") {
    return (
      <ul className="grid grid-cols-2 gap-x-5 gap-y-6 lg:grid-cols-1 lg:gap-5">
        {items.map((f) => {
          const absent = f.available === false;
          const unknown = f.available === null;
          const Icon = facilityIcon[f.kind];
          return (
            <li key={f.kind} className="grid min-w-0 grid-cols-[24px_minmax(0,1fr)] items-start gap-x-3">
              <Icon
                width={22}
                height={22}
                className={`mt-0.5 shrink-0 ${absent ? "text-muted opacity-40" : unknown ? "text-muted opacity-30" : "text-teal"}`}
              />
              <div className="min-w-0">
                <p className={`text-ui font-medium leading-snug ${absent ? "text-muted line-through" : "text-ink"}`}>
                  {f.title}
                </p>
                <p className={`mt-1 text-caption leading-snug ${absent || unknown ? "text-muted" : "text-ink-soft"}`}>
                  {absent ? "Nicht vorhanden" : f.note}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    );
  }

  if (variant === "rail") {
    return (
      <div>
        <p className="text-data-label uppercase text-teal">Vor Ort</p>
        <dl className="mt-4 divide-y divide-line">
          {items.map((f) => {
            const Icon = facilityIcon[f.kind];
            const absent = f.available === false;
            const unknown = f.available === null;
            return (
              <div key={f.kind} className="flex items-center justify-between gap-6 py-4">
                <dt className="flex items-center gap-3">
                  <Icon
                    width={18}
                    height={18}
                    className={`text-ink-soft ${absent ? "opacity-40" : unknown ? "opacity-30" : ""}`}
                  />
                  <span className={`text-body font-medium ${absent ? "text-muted line-through" : "text-ink"}`}>
                    {f.title}
                  </span>
                </dt>
                <dd className="text-caption text-muted">{f.note}</dd>
              </div>
            );
          })}
        </dl>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-8 md:grid-cols-3">
      {items.map((f) => {
        const Icon = facilityIcon[f.kind];
        const absent = f.available === false;
        const unknown = f.available === null;
        return (
          <div key={f.kind}>
            <span
              className={`grid h-11 w-11 place-items-center rounded-[14px] bg-ink/[0.04] text-ink ${
                absent ? "opacity-40" : unknown ? "opacity-30" : ""
              }`}
            >
              <Icon width={22} height={22} />
            </span>
            <p className={`mt-3 text-ui font-medium leading-tight ${absent ? "text-muted line-through" : "text-ink"}`}>
              {f.title}
            </p>
            <p className="mt-0.5 text-caption leading-snug text-muted">{f.note}</p>
          </div>
        );
      })}
    </div>
  );
}
