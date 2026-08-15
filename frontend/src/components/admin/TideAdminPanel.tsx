import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  getTideProfile,
  recalculateTides,
  updateTideProfile,
  type TideProfile,
  type TideEvent,
} from "../../lib/api";
import { Field, fieldClass } from "../ui";

// Operator UI: enter the observed HH:MM for the next high and low water,
// enter a technical note, save. The panel translates the entered clock
// time back into the storable offset by comparing it against the model's
// raw (uncorrected) event time.
//
// Why not store the times directly? The tide profile applies a *general*
// offset to every future event of that type, not a per-event override —
// storing HH:MM would tie the correction to a single date. Comparing
// user_time against raw_time in the same day, modulo 24 h to stay within
// ±12 h, gives us the offset the backend already understands.

function extractHm(iso: string, timezone: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
}

function timeToMinutes(hm: string): number | null {
  const match = /^(\d{2}):(\d{2})$/.exec(hm);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

/** Compute the offset (minutes, ±12 h) that turns `raw_time` HH:MM into the
 *  user's entered HH:MM. Modular so a small crossing over midnight
 *  (e.g. raw 23:55, user 00:05 = +10 min) stays a small positive delta
 *  rather than a −23:50 h leap. */
function offsetFromEnteredTime(
  userHm: string,
  rawIso: string,
  timezone: string,
): number | null {
  const userMin = timeToMinutes(userHm);
  const rawMin = timeToMinutes(extractHm(rawIso, timezone));
  if (userMin === null || rawMin === null) return null;
  let delta = ((userMin - rawMin) % 1440 + 1440) % 1440;
  if (delta > 720) delta -= 1440;
  return delta;
}

function nextEvent(events: TideEvent[] | undefined, type: "high" | "low"): TideEvent | undefined {
  return (events ?? []).find((e) => e.event_type === type);
}

export default function TideAdminPanel({ spotId }: {
  spotId: string;
  /** Kept in the type for call-site compatibility; not used in the lean UI. */
  spotLat?: number;
  spotLon?: number;
}) {
  const [profile, setProfile] = useState<TideProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [highTime, setHighTime] = useState("");
  const [lowTime, setLowTime] = useState("");
  const [note, setNote] = useState("");

  const seed = useCallback((data: TideProfile) => {
    setProfile(data);
    setNote(data.note ?? "");
    if (data.timezone) {
      const nh = nextEvent(data.events, "high");
      const nl = nextEvent(data.events, "low");
      setHighTime(nh ? extractHm(nh.time, data.timezone) : "");
      setLowTime(nl ? extractHm(nl.time, data.timezone) : "");
    }
  }, []);

  const reload = useCallback(async () => {
    try {
      const data = await getTideProfile(spotId);
      seed(data);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Gezeiten konnten nicht geladen werden.",
      );
    }
  }, [seed, spotId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const run = async (work: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await work();
      setMessage(success);
      await reload();
    } catch (cause) {
      setError(
        cause instanceof ApiError || cause instanceof Error
          ? cause.message
          : "Aktion fehlgeschlagen.",
      );
    } finally {
      setBusy(false);
    }
  };

  const nextHigh = useMemo(() => nextEvent(profile?.events, "high"), [profile]);
  const nextLow = useMemo(() => nextEvent(profile?.events, "low"), [profile]);
  const tz = profile?.timezone ?? "";
  const canComputeOffsets = Boolean(tz && (nextHigh || nextLow));

  if (!profile) {
    return (
      <>
        <p className="text-label text-admin-fg2">Gezeiten werden geladen.</p>
        {error && <p className="mt-2 text-label text-red-600">{error}</p>}
      </>
    );
  }

  const onSave = () => {
    if (!canComputeOffsets) {
      setError(
        'Für die Zeit-Eingabe muss zuerst eine Berechnung vorliegen. Bitte „Neu berechnen" ausführen.',
      );
      return;
    }
    // Only touch the offsets the operator actually filled in.
    const changes: Record<string, unknown> = { note: note || null, correction_reason: note || null };
    if (highTime && nextHigh) {
      const delta = offsetFromEnteredTime(highTime, nextHigh.raw_time ?? nextHigh.time, tz);
      if (delta === null) {
        setError("Ungültige Uhrzeit für Hochwasser.");
        return;
      }
      changes.high_offset_minutes = delta;
    }
    if (lowTime && nextLow) {
      const delta = offsetFromEnteredTime(lowTime, nextLow.raw_time ?? nextLow.time, tz);
      if (delta === null) {
        setError("Ungültige Uhrzeit für Niedrigwasser.");
        return;
      }
      changes.low_offset_minutes = delta;
    }
    void run(() => updateTideProfile(spotId, changes), "Korrektur gespeichert.");
  };

  const onRecalc = () =>
    run(() => recalculateTides(spotId), "Neuberechnung wurde eingeplant.");

  const onReset = () => {
    // Reset to the current model prediction (offsets = 0) so the next save
    // lands neutral. Note stays; if the operator wants to clear it, they can.
    if (nextHigh && tz) setHighTime(extractHm(nextHigh.raw_time ?? nextHigh.time, tz));
    if (nextLow && tz) setLowTime(extractHm(nextLow.raw_time ?? nextLow.time, tz));
    setMessage(null);
    setError(null);
  };

  const predictedHigh = nextHigh && tz ? extractHm(nextHigh.raw_time ?? nextHigh.time, tz) : null;
  const predictedLow = nextLow && tz ? extractHm(nextLow.raw_time ?? nextLow.time, tz) : null;

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="border-l-2 border-admin-danger-border pl-3 text-label text-red-700">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="border-l-2 border-admin-success pl-3 text-label text-admin-success">
          {message}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Uhrzeit Hochwasser"
          hint={
            predictedHigh
              ? `Modellvorhersage ${predictedHigh}. Beobachtete Zeit eintragen — der Offset wird automatisch berechnet.`
              : 'Noch keine Vorhersage — bitte zuerst „Neu berechnen" ausführen.'
          }
        >
          <input
            className={fieldClass}
            type="time"
            value={highTime}
            onChange={(e) => setHighTime(e.target.value)}
            disabled={!predictedHigh}
          />
        </Field>
        <Field
          label="Uhrzeit Niedrigwasser"
          hint={
            predictedLow
              ? `Modellvorhersage ${predictedLow}. Beobachtete Zeit eintragen — der Offset wird automatisch berechnet.`
              : 'Noch keine Vorhersage — bitte zuerst „Neu berechnen" ausführen.'
          }
        >
          <input
            className={fieldClass}
            type="time"
            value={lowTime}
            onChange={(e) => setLowTime(e.target.value)}
            disabled={!predictedLow}
          />
        </Field>
      </div>

      <Field label="Fachliche Notiz">
        <textarea
          className={fieldClass}
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Field>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onSave}
          className="rounded-md bg-admin-accent px-3 py-2 text-label font-medium text-white disabled:opacity-50"
        >
          Korrektur speichern
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onRecalc}
          className="rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50"
        >
          Neu berechnen
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onReset}
          className="rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50"
        >
          Korrektur zurücksetzen
        </button>
      </div>
    </div>
  );
}
