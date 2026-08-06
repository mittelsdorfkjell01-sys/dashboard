import { useEffect, useMemo, useState } from "react";
import { getSpotTides, type PublicTides, type PublicTideEvent } from "../lib/api";
import { formatTideTime } from "../lib/tideTime";

export { formatTideTime } from "../lib/tideTime";

const PHASE_LABELS: Record<PublicTides["phase"], string> = {
  rising: "Steigend",
  high: "Hochwasser",
  falling: "Fallend",
  low: "Niedrigwasser",
  unavailable: "Nicht verfügbar",
};

function EventTime({ event, timezone, prominent = false }: {
  event: PublicTideEvent; timezone: string; prominent?: boolean;
}) {
  const shown = formatTideTime(event.time, timezone, event.uncertainty_minutes);
  return (
    <div className={prominent ? "min-w-0 border-l-2 border-teal pl-3" : "grid grid-cols-[5.5rem_1fr] items-baseline gap-3"}>
      <p className="text-caption font-medium uppercase text-muted">
        {event.event_type === "high" ? "Hochwasser" : "Niedrigwasser"}
      </p>
      <div className={prominent ? "mt-1" : "min-w-0"}>
        <p className={`${prominent ? "text-ui" : "text-label"} font-semibold text-ink`}>{shown.time}</p>
        <p className="text-caption text-muted">{shown.date}</p>
      </div>
    </div>
  );
}

export default function TidePanel({ spotId }: { spotId: string }) {
  const [data, setData] = useState<PublicTides | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    getSpotTides(spotId)
      .then((result) => active && setData(result))
      .catch(() => active && setData({
        available: false,
        message: "Für diesen Spot sind derzeit keine verlässlichen Gezeitenangaben verfügbar.",
        timezone: null, phase: "unavailable", cycle_position: null,
        quality: "unavailable", approximate: true, last_calculated_at: null,
        valid_until: null, events: [],
      }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [spotId]);

  const next = useMemo(() => ({
    high: data?.events.find((item) => item.event_type === "high"),
    low: data?.events.find((item) => item.event_type === "low"),
  }), [data]);

  if (loading) return <div className="h-28 animate-pulse bg-line" aria-label="Gezeiten werden geladen" />;
  if (!data?.available || !data.timezone) {
    return <p className="py-5 text-body text-ink-soft">{data?.message ?? "Für diesen Spot sind derzeit keine verlässlichen Gezeitenangaben verfügbar."}</p>;
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(15rem,1fr)_minmax(18rem,1.4fr)]">
      <div className="min-w-0">
        <div className="flex items-center justify-between gap-4 border-b border-line pb-3">
          <div>
            <p className="text-caption uppercase text-muted">Aktuelle Tide</p>
            <p className="mt-1 text-ui font-semibold text-ink">{PHASE_LABELS[data.phase]}</p>
          </div>
          {data.cycle_position !== null && data.phase !== "high" && data.phase !== "low" && (
            <div
              className="h-1.5 w-24 overflow-hidden bg-line"
              role="progressbar"
              aria-label="Position im Tidezyklus"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(data.cycle_position * 100)}
            >
              <div className="h-full bg-teal" style={{ width: `${Math.round(data.cycle_position * 100)}%` }} />
            </div>
          )}
        </div>
        <div className="grid gap-5 py-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          {next.high && <EventTime event={next.high} timezone={data.timezone} prominent />}
          {next.low && <EventTime event={next.low} timezone={data.timezone} prominent />}
        </div>
        <p className="text-caption leading-relaxed text-muted">
          Astronomische Prognose, ungefähr und gegebenenfalls lokal korrigiert. Wetter, Sturmflut, Abfluss und Strömung können abweichen.
        </p>
        <p className="mt-2 text-caption text-muted">Berechnet mit FES2022, bereitgestellt durch AVISO+ und CNES.</p>
      </div>
      <div className="min-w-0 border-t border-line pt-3 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
        <p className="mb-3 text-caption font-medium uppercase text-muted">Nächste Ereignisse</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {data.events.slice(0, 6).map((event) => (
            <EventTime key={event.id} event={event} timezone={data.timezone!} />
          ))}
        </div>
        {data.last_calculated_at && (
          <p className="mt-4 text-caption text-muted">
            Zuletzt berechnet: {new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: data.timezone }).format(new Date(data.last_calculated_at))}
          </p>
        )}
        {data.message && <p className="mt-2 text-caption text-amber-700">{data.message}</p>}
      </div>
    </div>
  );
}
