import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getTideProfile,
  recalculateTides,
  updateTideProfile,
  type TideProfile,
} from "../../lib/api";
import { Field, fieldClass } from "../ui";

// Stripped-down control surface: two offset fields (high / low water), a
// technical note, and three buttons. Anchor management, calibration
// history, event overrides and the model preview are handled elsewhere or
// by the worker and don't need to sit on this operator's daily editor.

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
  const [highOffset, setHighOffset] = useState(0);
  const [lowOffset, setLowOffset] = useState(0);
  const [note, setNote] = useState("");

  const seed = useCallback((data: TideProfile) => {
    setProfile(data);
    setHighOffset(data.high_offset_minutes);
    setLowOffset(data.low_offset_minutes);
    setNote(data.note ?? "");
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

  if (!profile) {
    return (
      <>
        <p className="text-label text-admin-fg2">Gezeiten werden geladen.</p>
        {error && <p className="mt-2 text-label text-red-600">{error}</p>}
      </>
    );
  }

  const onSave = () =>
    run(
      () =>
        // The backend requires `correction_reason` for large offsets — reuse the
        // note here so the operator's single free-text field satisfies both the
        // documentation and the validation gate.
        updateTideProfile(spotId, {
          high_offset_minutes: highOffset,
          low_offset_minutes: lowOffset,
          note: note || null,
          correction_reason: note || null,
        }),
      "Korrektur gespeichert.",
    );

  const onRecalc = () =>
    run(() => recalculateTides(spotId), "Neuberechnung wurde eingeplant.");

  const onReset = () => {
    setHighOffset(0);
    setLowOffset(0);
    setNote("");
    setMessage(null);
    setError(null);
  };

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="border-l-2 border-red-500 pl-3 text-label text-red-700">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="border-l-2 border-admin-success pl-3 text-label text-admin-success">
          {message}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Uhrzeit Hochwasser (Min. verschieben)">
          <input
            className={fieldClass}
            type="number"
            value={highOffset}
            onChange={(e) => setHighOffset(Number(e.target.value))}
          />
        </Field>
        <Field label="Uhrzeit Niedrigwasser (Min. verschieben)">
          <input
            className={fieldClass}
            type="number"
            value={lowOffset}
            onChange={(e) => setLowOffset(Number(e.target.value))}
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
