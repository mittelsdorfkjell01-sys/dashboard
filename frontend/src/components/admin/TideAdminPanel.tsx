import { useCallback, useEffect, useMemo, useState } from "react";
import {
  autoSelectTideAnchor,
  getTideProfile,
  recalculateTides,
  updateTideProfile,
  type TideProfile,
  type TideEvent,
} from "../../lib/api/tides";
import { ApiError } from "../../lib/api/client";
import { Field, fieldClass } from "../ui";
import { Button } from "./ui";

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

export default function TideAdminPanel({ spotId, onChanged }: {
  spotId: string;
  onChanged?: () => void | Promise<void>;
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
      await onChanged?.();
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
        {error && <p className="mt-2 text-label text-admin-danger">{error}</p>}
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

  const onActivate = () => run(async () => {
    await updateTideProfile(spotId, { enabled: true, public_enabled: false });
    await autoSelectTideAnchor(spotId);
  }, "FES-Berechnung und automatische Ankerwahl wurden eingeplant.");

  const onReviewAnchor = () => run(
    () => updateTideProfile(spotId, { review_anchor: true }),
    "Modellanker wurde geprüft. Die bestätigte Berechnung läuft erneut.",
  );

  const onPublication = (publicEnabled: boolean) => run(
    () => updateTideProfile(spotId, { public_enabled: publicEnabled }),
    publicEnabled ? "Astronomische Tide wurde veröffentlicht." : "Astronomische Tide wurde zurückgezogen.",
  );

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
        <p role="alert" className="border-l-2 border-admin-danger-border pl-3 text-label text-admin-danger">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="border-l-2 border-admin-success pl-3 text-label text-admin-success">
          {message}
        </p>
      )}

      <dl className="grid gap-x-4 gap-y-2 border-y border-admin-border py-3 text-label sm:grid-cols-2">
        <div>
          <dt className="text-admin-muted">Berechnung</dt>
          <dd className="mt-0.5 font-medium text-admin-fg">{CALCULATION_LABELS[profile.calculation_status]}</dd>
        </div>
        <div>
          <dt className="text-admin-muted">Modellanker</dt>
          <dd className="mt-0.5 font-medium text-admin-fg">{ANCHOR_LABELS[profile.anchor_status]}</dd>
        </div>
        {profile.anchor_distance_m !== null && (
          <div>
            <dt className="text-admin-muted">Entfernung zum Spot</dt>
            <dd className="mt-0.5 font-medium tabular-nums text-admin-fg">{Math.round(profile.anchor_distance_m)} m</dd>
          </div>
        )}
        <div>
          <dt className="text-admin-muted">Öffentlich</dt>
          <dd className="mt-0.5 font-medium text-admin-fg">{profile.public_enabled ? "Ja · FES ersetzt den Fallback" : "Nein · Fallback bleibt aktiv"}</dd>
        </div>
      </dl>

      {(profile.anchor_warnings ?? []).map((warning) => (
        <p key={warning} className="rounded-md bg-admin-warning-bg px-3 py-2 text-label text-admin-warning">
          {warning}
        </p>
      ))}
      {profile.calculation_error && (
        <p className="rounded-md bg-admin-danger-bg px-3 py-2 text-label text-admin-danger">
          {profile.calculation_error} Erneut einplanen oder Modellanker prüfen.
        </p>
      )}

      {!profile.enabled && (
        <div>
          <p className="mb-2 text-label text-admin-fg2">Startet eine private FES-Berechnung. Es wird noch nichts veröffentlicht.</p>
          <Button variant="primary" disabled={busy} onClick={onActivate}>FES für diesen Spot aktivieren</Button>
        </div>
      )}

      {profile.enabled && profile.anchor_status === "auto_selected" && profile.calculation_status === "ready" && (
        <div>
          <p className="mb-2 text-label text-admin-fg2">Prüfe Entfernung und Warnungen. Die Bestätigung veröffentlicht noch nichts.</p>
          <Button variant="primary" disabled={busy} onClick={onReviewAnchor}>Modellanker bestätigen</Button>
        </div>
      )}

      {profile.enabled && profile.anchor_status === "reviewed" && profile.calculation_status === "ready" && (
        <div>
          <p className="mb-2 text-label text-admin-fg2">
            {profile.public_enabled
              ? "Die geprüfte FES-Tide ist öffentlich und ersetzt den Meeresspiegel-Fallback."
              : "Die geprüfte Tide bleibt privat, bis sie ausdrücklich veröffentlicht wird."}
          </p>
          <Button
            variant={profile.public_enabled ? "secondary" : "primary"}
            disabled={busy}
            onClick={() => onPublication(!profile.public_enabled)}
          >
            {profile.public_enabled ? "Tide zurückziehen" : "Astronomische Tide veröffentlichen"}
          </Button>
        </div>
      )}

      {profile.enabled && <div className="grid gap-3 sm:grid-cols-2">
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
      </div>}

      {profile.enabled && <Field label="Fachliche Notiz">
        <textarea
          className={fieldClass}
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Field>}

      {profile.enabled && <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={busy} onClick={onSave}>
          Korrektur speichern
        </Button>
        <Button variant="secondary" disabled={busy} onClick={onRecalc}>
          Neu berechnen
        </Button>
        <Button variant="secondary" disabled={busy} onClick={onReset}>
          Korrektur zurücksetzen
        </Button>
      </div>}
    </div>
  );
}

const CALCULATION_LABELS: Record<TideProfile["calculation_status"], string> = {
  not_configured: "Noch nicht konfiguriert",
  queued: "Eingeplant",
  running: "Läuft",
  ready: "Bereit",
  failed: "Fehlgeschlagen",
  stale: "Veraltet",
};

const ANCHOR_LABELS: Record<TideProfile["anchor_status"], string> = {
  needs_review: "Auswahl ausstehend",
  auto_selected: "Automatisch gewählt · Prüfung nötig",
  reviewed: "Geprüft",
  invalid: "Ungültig",
};
