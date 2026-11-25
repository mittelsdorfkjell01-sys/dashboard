import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../../lib/api";
import type { Spot } from "../../lib/types";
import { sportLabelShort } from "../../lib/labels";
import { spotPath } from "../../lib/spotRoutes";
import { windColor } from "../../lib/windScale";
import Segmented from "../ui/Segmented";

const MONTHS_SHORT = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

type Floor = "10" | "15" | "20";
const FLOOR_WINDOWS: Record<Floor, api.WindWindowKey[]> = {
  "10": ["10_15", "15_20", "20_30", "30_plus"],
  "15": ["15_20", "20_30", "30_plus"],
  "20": ["20_30", "30_plus"],
};

type Shares = { state: "ready"; months: (number | null)[] } | { state: "loading" | "missing" | "error" };

// One fetch per spot for the whole visit; switching views or wind floor
// recomputes from the same payload.
const cache = new Map<string, Promise<api.WindClimatologyRead>>();
function load(id: string) {
  let hit = cache.get(id);
  if (!hit) {
    hit = api.getWindClimatology(id);
    hit.catch(() => cache.delete(id));
    cache.set(id, hit);
  }
  return hit;
}

/** Share of daylight hours at or above the floor, per month (mean of the
 *  month's quarter-month sections), from the V2 climatology payload. */
function monthShares(data: api.WindClimatologyRead, floor: Floor): (number | null)[] {
  const months: (number | null)[] = Array.from({ length: 12 }, () => null);
  const sections = data.sections ?? [];
  for (let m = 1; m <= 12; m += 1) {
    const own = sections.filter((s) => s.month === m);
    const values = own
      .map((s) => FLOOR_WINDOWS[floor].reduce<number | null>((sum, key) => {
        const v = s.windows[key]?.percent;
        if (typeof v !== "number" || !Number.isFinite(v) || sum == null) return null;
        return sum + v;
      }, 0))
      .filter((v): v is number => v != null);
    months[m - 1] = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  }
  return months;
}

/** Fetches the climatology for the given spots, at most four at a time. */
function useClimatologies(ids: string[]) {
  const [data, setData] = useState<Record<string, api.WindClimatologyRead | "error">>({});
  const key = ids.join("|");
  useEffect(() => {
    let alive = true;
    const queue = key ? key.split("|") : [];
    const worker = async () => {
      while (alive && queue.length) {
        const id = queue.shift()!;
        try {
          const result = await load(id);
          if (alive) setData((current) => ({ ...current, [id]: result }));
        } catch {
          if (alive) setData((current) => ({ ...current, [id]: "error" }));
        }
      }
    };
    void Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker));
    return () => { alive = false; };
  }, [key]);
  return data;
}

/**
 * Results grouped by region, each spot with a strip of its twelve wind
 * months (chosen 2026-11-24, the right-hand view of the results toggle).
 * The searched month is outlined; the figure on the right is that month's
 * share of daylight hours at or above the chosen wind. Informs, does not
 * rank spots by quality — sorting by that month is the visitor's choice.
 */
export default function RegionWindView({ spots, month }: { spots: Spot[]; month: number }) {
  const [floor, setFloor] = useState<Floor>("15");
  const [sort, setSort] = useState<"month" | "name">("month");
  const ids = useMemo(() => spots.map((s) => s.id), [spots]);
  const raw = useClimatologies(ids);

  const shares = useMemo(() => {
    const out = new Map<string, Shares>();
    for (const spot of spots) {
      const entry = raw[spot.id];
      if (!entry) out.set(spot.id, { state: "loading" });
      else if (entry === "error") out.set(spot.id, { state: "error" });
      else if (entry.status !== "ready" || !entry.sections?.length) out.set(spot.id, { state: "missing" });
      else out.set(spot.id, { state: "ready", months: monthShares(entry, floor) });
    }
    return out;
  }, [spots, raw, floor]);

  const monthValue = (spot: Spot) => {
    const s = shares.get(spot.id);
    return s?.state === "ready" ? s.months[month - 1] ?? null : null;
  };

  const groups = useMemo(() => {
    const sorted = [...spots].sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name, "de");
      return (monthValue(b) ?? -1) - (monthValue(a) ?? -1);
    });
    const byRegion = new Map<string, Spot[]>();
    for (const spot of sorted) {
      const region = spot.regionName || spot.region || "Ohne Region";
      byRegion.set(region, [...(byRegion.get(region) ?? []), spot]);
    }
    return [...byRegion.entries()];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spots, sort, shares, month]);

  const max = 60; // share scale ceiling (%), so tones compare across spots

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented<Floor>
          label="Wind ab"
          value={floor}
          onChange={setFloor}
          options={[
            { id: "10", label: "ab 10 kn" },
            { id: "15", label: "ab 15 kn" },
            { id: "20", label: "ab 20 kn" },
          ]}
        />
        <Segmented<"month" | "name">
          label="Sortieren"
          value={sort}
          onChange={setSort}
          options={[
            { id: "month", label: `${MONTHS[month - 1]}-Wind` },
            { id: "name", label: "Name" },
          ]}
        />
      </div>

      <div className="mt-6 grid gap-8">
        {groups.map(([region, list]) => (
          <section key={region} aria-label={region}>
            <div className="flex items-baseline justify-between gap-3 border-b border-line pb-2">
              <h2 className="text-lead font-semibold text-ink">{region}</h2>
              <span className="text-caption text-muted">{list.length} {list.length === 1 ? "Spot" : "Spots"}</span>
            </div>
            <div className="mt-1 grid gap-0.5">
              {list.map((spot) => {
                const s = shares.get(spot.id) ?? { state: "loading" as const };
                const value = monthValue(spot);
                const sports = (spot.sports ?? []).map(sportLabelShort).join(" · ");
                return (
                  <Link
                    key={spot.id}
                    to={spotPath(spot, "daten")}
                    className="grid grid-cols-[minmax(0,1fr)_3.5rem] items-center gap-x-4 gap-y-2 rounded-card px-2 py-2.5 transition-colors duration-fast hover:bg-tile sm:grid-cols-[minmax(0,1.2fr)_minmax(13rem,2fr)_4rem]"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-body font-semibold text-ink">{spot.name}</span>
                      {sports && <span className="block truncate text-caption text-muted">{sports}</span>}
                    </span>
                    <span className="col-span-2 row-start-2 min-w-0 sm:col-span-1 sm:col-start-2 sm:row-start-1">
                      {s.state === "ready" ? (
                        <span className="grid grid-cols-12 gap-0.5" role="img" aria-label={`Windanteil ab ${floor} kn je Monat, ${MONTHS[month - 1]} ${value == null ? "ohne Wert" : `${Math.round(value)} Prozent`}`}>
                          {s.months.map((v, i) => (
                            <span
                              key={i}
                              className={`h-5 rounded-[4px] ${i === month - 1 ? "outline outline-2 outline-offset-1 outline-ink" : ""}`}
                              style={{ background: v == null ? "var(--sw-band)" : `color-mix(in oklab, ${windColor(Number(floor))} ${Math.round(12 + Math.min(1, v / max) * 88)}%, var(--sw-band))` }}
                            />
                          ))}
                        </span>
                      ) : (
                        <span className={`block h-5 rounded-[4px] bg-band ${s.state === "loading" ? "animate-pulse" : ""}`} aria-hidden={s.state === "loading"}>
                          {s.state !== "loading" && (
                            <span className="flex h-full items-center px-2 text-caption text-muted">
                              {s.state === "missing" ? "Windmonate noch nicht berechnet" : "Windmonate nicht verfügbar"}
                            </span>
                          )}
                        </span>
                      )}
                      <span className="mt-0.5 grid grid-cols-12 gap-0.5 text-center text-micro text-muted" aria-hidden="true">
                        {MONTHS_SHORT.map((m, i) => <span key={i} className={i === month - 1 ? "font-semibold text-ink" : ""}>{m}</span>)}
                      </span>
                    </span>
                    <span className="text-right sm:col-start-3 sm:row-start-1">
                      <span className="block font-figures text-lead font-bold tabular-nums text-ink">{value == null ? "–" : `${Math.round(value)} %`}</span>
                      <span className="block text-micro text-muted">im {MONTHS[month - 1]}</span>
                    </span>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      <p className="mt-6 text-data-caption text-muted">
        Farbtiefe = Anteil der Tageslichtstunden mit Wind ab {floor} kn, je Monat · umrandet = {MONTHS[month - 1]} · ERA5, 10 m. Windrichtung und lokale Bedingungen sind nicht berücksichtigt.
      </p>
    </div>
  );
}
