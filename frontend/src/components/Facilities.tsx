import type { Facility, FacilityKind } from "../lib/types";
import {
  ChangingRoomIcon,
  CheckCircleIcon,
  CloseIcon,
  FoodIcon,
  MinusIcon,
  ParkingIcon,
  ShowerIcon,
  SurfSchoolIcon,
  ToiletIcon,
} from "../lib/icons";

const facilityIcon: Record<FacilityKind, (p: { width?: number; height?: number; className?: string }) => JSX.Element> = {
  parking: ParkingIcon,
  school: SurfSchoolIcon,
  shower: ShowerIcon,
  toilet: ToiletIcon,
  changing: ChangingRoomIcon,
  food: FoodIcon,
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
 *  `variant="grid"` (default) is the icon-tile grid; `variant="table"` is the
 *  hairline spec sheet that forms the foot of the Info tab's profile card —
 *  one row per amenity, state carried by the right-hand glyph (✓ / ✗ / –)
 *  rather than a strikethrough, since the glyph already names all three
 *  states; `variant="rail"` is the
 *  hairline-table look for the sticky spec rail next to the lede; `variant="list"`
 *  is the calm facts list and `variant="compact"` is its denser profile-panel
 *  counterpart.
 */
export default function Facilities({
  items,
  variant = "grid",
}: {
  items: Facility[];
  variant?: "grid" | "rail" | "list" | "compact" | "icons" | "table";
}) {
  if (items.length === 0) return null;

  if (variant === "table") {
    return (
      <table className="w-full" aria-label="Ausstattung am Spot">
        <thead className="sr-only">
          <tr>
            <th scope="col">Ausstattung</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody className="flex flex-col divide-y divide-line">
          {items.map((f) => {
            const Icon = facilityIcon[f.kind];
            const absent = f.available === false;
            const unknown = f.available === null;
            const status = f.available === true ? "Vorhanden" : absent ? "Nicht vorhanden" : "Keine Angabe";
            return (
              <tr key={f.kind} className="flex min-w-0 items-center justify-between gap-3 py-2">
                <th scope="row" className="min-w-0 text-left font-normal">
                  <span className="flex min-w-0 items-center gap-2.5">
                    <Icon
                      width={16}
                      height={16}
                      className={`shrink-0 ${absent ? "text-muted opacity-50" : unknown ? "text-muted opacity-40" : "text-ink-soft"}`}
                    />
                    <span
                      className={`break-words text-caption font-medium leading-tight ${absent ? "text-muted" : unknown ? "text-muted" : "text-ink"}`}
                    >
                      {f.title}
                    </span>
                  </span>
                </th>
                <td className="text-right">
                  <span
                    className={`inline-grid h-5 w-5 place-items-center ${f.available === true ? "text-ink" : "text-muted"}`}
                    aria-label={status}
                    title={status}
                  >
                    {f.available === true ? (
                      <CheckCircleIcon checkOnly width={14} height={14} aria-hidden />
                    ) : absent ? (
                      <CloseIcon width={14} height={14} aria-hidden />
                    ) : (
                      <MinusIcon width={14} height={14} aria-hidden />
                    )}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

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
                className={`flex h-8 w-8 items-center justify-center rounded-card bg-band ${
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

  if (variant === "list" || variant === "compact") {
    const compact = variant === "compact";
    return (
      <ul className={`grid grid-cols-2 gap-x-5 ${compact ? "gap-y-3.5" : "gap-y-5"}`}>
        {items.map((f) => {
          const absent = f.available === false;
          const unknown = f.available === null;
          const Icon = facilityIcon[f.kind];
          return (
            <li key={f.kind} className={`grid min-w-0 items-start ${compact ? "grid-cols-[20px_minmax(0,1fr)] gap-x-2.5" : "grid-cols-[24px_minmax(0,1fr)] gap-x-3"}`}>
              <Icon
                width={compact ? 19 : 22}
                height={compact ? 19 : 22}
                className={`mt-0.5 shrink-0 ${absent ? "text-muted opacity-40" : unknown ? "text-muted opacity-30" : "text-ink"}`}
              />
              <div className="min-w-0">
                <p className={`${compact ? "text-caption" : "text-ui"} font-medium leading-snug ${absent ? "text-muted line-through" : "text-ink"}`}>
                  {f.title}
                </p>
                <p className={`${compact ? "mt-0.5" : "mt-1"} text-caption leading-snug ${absent || unknown ? "text-muted" : "text-ink-soft"}`}>
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
        <p className="text-data-label uppercase text-ink">Vor Ort</p>
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
              className={`grid h-11 w-11 place-items-center rounded-card bg-ink/[0.04] text-ink ${
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
