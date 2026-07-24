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
 *  hairline-table look for the sticky spec rail next to the lede.
 */
export default function Facilities({
  items,
  variant = "grid",
}: {
  items: Facility[];
  variant?: "grid" | "rail";
}) {
  if (items.length === 0) return null;

  if (variant === "rail") {
    return (
      <div>
        <p className="text-caption font-medium uppercase tracking-[0.18em] text-teal">
          Vor Ort
        </p>
        <dl className="mt-4 divide-y divide-line border-t border-line">
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
    <div className="grid grid-cols-2 gap-x-12 gap-y-8 md:grid-cols-3">
      {items.map((f) => {
        const Icon = facilityIcon[f.kind];
        const absent = f.available === false;
        const unknown = f.available === null;
        return (
          <div key={f.kind}>
            <span
              className={`grid h-11 w-11 place-items-center rounded-full bg-ink/[0.04] text-ink ${
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
