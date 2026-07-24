import type { LiveConditions as Live } from "../lib/types";
import { degToCompass } from "./WindRose";

/** One reading: small label above, value + unit below. */
function Stat({
  label,
  value,
  unit,
  accent,
}: {
  label: string;
  value: string;
  unit?: string;
  accent?: boolean;
}) {
  return (
    <div className="w-[76px]">
      <p className="text-[10.5px] font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 flex items-baseline gap-1">
        <span className={`text-[20px] font-semibold leading-none ${accent ? "text-[#2F6FB0]" : "text-ink"}`}>
          {value}
        </span>
        {unit && <span className="text-[12px] font-medium text-muted">{unit}</span>}
      </p>
    </div>
  );
}

/** A titled group with two readings side by side. */
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto w-fit">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{title}</p>
      <div className="flex gap-x-8">{children}</div>
    </div>
  );
}

/** "Aktuelle Bedingungen" — Wind / Wasser / Luft, each with two readings.
 *  Box height matches the map (360 px); width stays with the grid column. */
export default function LiveConditions({ live }: { live: Live }) {
  return (
    <div className="flex h-[360px] flex-col rounded-lg border-[0.3px] border-ink p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-orange" />
        <h2 className="text-[15px] font-semibold text-ink">Aktuelle Bedingungen</h2>
      </div>

      <div className="flex flex-1 flex-col justify-evenly">
        <Group title="Wind">
          <Stat label="Stärke" value={String(live.wind)} unit="kts" />
          <Stat label="Böen" value={String(live.gust)} unit="kts" />
        </Group>

        <Group title="Wasser">
          <Stat label="Welle" value={live.wave.toFixed(1)} unit="m" accent />
          <Stat label="Temp" value={String(live.waterTemp)} unit="°C" />
        </Group>

        <Group title="Luft">
          <Stat label="Temp" value={String(live.airTemp)} unit="°C" />
          <Stat label="Richtung" value={degToCompass(live.windDir)} unit={`${Math.round(live.windDir)}°`} />
        </Group>
      </div>
    </div>
  );
}
