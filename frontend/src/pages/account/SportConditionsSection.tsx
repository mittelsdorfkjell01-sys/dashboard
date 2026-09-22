import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../../context/AuthContext";
import { AccountError, updatePreferences, type SportConditions, type SportKey } from "../../lib/account";
import { SPORTS, sportLabel } from "../../lib/labels";
import { Button, Field, Input } from "../../components/ui";

type Profiles = Partial<Record<SportKey, SportConditions>>;
type ConditionField = keyof SportConditions;

const FIELDS: ConditionField[] = ["windMinKn", "windMaxKn", "waveMinM", "waveMaxM", "waterTempMinC"];

function cleanProfiles(profiles: Profiles): Profiles {
  const clean: Profiles = {};
  for (const sport of SPORTS) {
    const source = profiles[sport];
    if (!source) continue;
    const values: SportConditions = {};
    for (const field of FIELDS) {
      if (source[field] != null) values[field] = source[field];
    }
    if (Object.keys(values).length) clean[sport] = values;
  }
  return clean;
}

function selectedSports(sports: string[] | undefined): SportKey[] {
  return SPORTS.filter((sport) => sports?.includes(sport));
}

function signature(sports: SportKey[], profiles: Profiles): string {
  return JSON.stringify({ sports: selectedSports(sports), conditions: cleanProfiles(profiles) });
}

function validationError(profiles: Profiles): string | null {
  const limits: { field: ConditionField; min: number; max: number }[] = [
    { field: "windMinKn", min: 0, max: 80 }, { field: "windMaxKn", min: 0, max: 80 },
    { field: "waveMinM", min: 0, max: 12 }, { field: "waveMaxM", min: 0, max: 12 },
    { field: "waterTempMinC", min: -5, max: 40 },
  ];
  for (const sport of SPORTS) {
    const values = profiles[sport];
    if (!values) continue;
    for (const { field, min, max } of limits) {
      const value = values[field];
      if (value != null && (!Number.isFinite(value) || value < min || value > max)) {
        return `Prüfe die Werte für ${sportLabel(sport)}: Ein Grenzwert liegt außerhalb des erlaubten Bereichs.`;
      }
    }
    if (values.windMinKn != null && values.windMaxKn != null && values.windMinKn > values.windMaxKn) {
      return `Bei ${sportLabel(sport)} ist der minimale Wind höher als der maximale Wind.`;
    }
    if (values.waveMinM != null && values.waveMaxM != null && values.waveMinM > values.waveMaxM) {
      return `Bei ${sportLabel(sport)} ist die minimale Wellenhöhe höher als die maximale Wellenhöhe.`;
    }
  }
  return null;
}

export default function SportConditionsSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { user, setUser } = useAuth();
  const [sports, setSports] = useState<SportKey[]>(() => selectedSports(user?.preferences.sports));
  const [profiles, setProfiles] = useState<Profiles>(() => user?.preferences.conditions ?? {});
  const [active, setActive] = useState<SportKey | null>(() => selectedSports(user?.preferences.sports)[0] ?? null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const savedSports = selectedSports(user?.preferences.sports);
  const savedProfiles = user?.preferences.conditions ?? {};
  const dirty = signature(sports, profiles) !== signature(savedSports, savedProfiles);
  const invalid = validationError(profiles);

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  const toggleSport = (sport: SportKey) => {
    const next = sports.includes(sport) ? sports.filter((item) => item !== sport) : SPORTS.filter((item) => sports.includes(item) || item === sport);
    setSports(next);
    if (!next.includes(active as SportKey)) setActive(next[0] ?? null);
    else if (!active) setActive(sport);
    setNote(null);
  };

  const setCondition = (sport: SportKey, field: ConditionField, raw: string) => {
    setProfiles((current) => ({
      ...current,
      [sport]: { ...current[sport], [field]: raw === "" ? null : Number(raw) },
    }));
    setNote(null);
  };

  const reset = () => {
    setSports(savedSports);
    setProfiles(savedProfiles);
    setActive(savedSports[0] ?? null);
    setNote(null);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (invalid || !dirty || busy) return;
    setBusy(true);
    setNote(null);
    try {
      const updated = await updatePreferences({ sports, conditions: cleanProfiles(profiles) });
      setUser(updated);
      setProfiles(updated.preferences.conditions ?? {});
      setNote({ kind: "ok", text: "Sportarten und Bedingungen gespeichert." });
    } catch (error) {
      setNote({ kind: "error", text: error instanceof AccountError ? error.message : "Speichern fehlgeschlagen. Bitte versuche es erneut." });
    } finally {
      setBusy(false);
    }
  };

  const current = active ? profiles[active] ?? {} : {};
  return (
    <section className="border-t border-line pt-8 first:border-t-0 first:pt-0" aria-labelledby="sport-conditions-title">
      <h2 id="sport-conditions-title" className="text-sz-18 font-semibold text-ink">Sportarten & Bedingungen</h2>
      <p className="mt-1 max-w-[60ch] text-ui text-muted">Wähle deine Sportarten und lege fest, welche Bedingungen für dich passen.</p>
      <form onSubmit={save} className="mt-5 space-y-6">
        <fieldset>
          <legend className="text-label font-semibold text-ink">Meine Sportarten</legend>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {SPORTS.map((sport) => {
              const checked = sports.includes(sport);
              return <label key={sport} className={`flex min-h-12 cursor-pointer items-center gap-2 rounded-[14px] border px-3 text-label font-medium text-ink transition-colors focus-within:ring-2 focus-within:ring-teal ${checked ? "border-teal bg-band" : "border-line bg-surface hover:bg-band"}`}>
                <input type="checkbox" checked={checked} disabled={busy} onChange={() => toggleSport(sport)} className="h-4 w-4 accent-teal" />
                {sportLabel(sport)}
              </label>;
            })}
          </div>
        </fieldset>

        {sports.length === 0 ? <p className="rounded-[14px] border border-dashed border-line px-4 py-5 text-ui text-muted">Wähle eine Sportart, um persönliche Bedingungen festzulegen.</p> : <div className="border-t border-line pt-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-body font-semibold text-ink">Meine Bedingungen</h3>
            <p className="text-caption text-muted">Alle Grenzwerte sind optional.</p>
          </div>
          {sports.length > 1 && <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Sportart für Bedingungen wählen">
            {sports.map((sport) => <button key={sport} type="button" disabled={busy} onClick={() => setActive(sport)} aria-pressed={active === sport} className={`min-h-11 rounded-full px-4 text-label font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${active === sport ? "bg-ink text-surface" : "bg-band text-ink hover:bg-line"}`}>{sportLabel(sport)}</button>)}
          </div>}
          {active && <div role="group" className="mt-4 rounded-[14px] bg-band p-4 sm:p-5" aria-label={`Bedingungen für ${sportLabel(active)}`}>
            <p className="mb-4 text-label font-semibold text-ink">{sportLabel(active)}</p>
            <div className="grid gap-5 sm:grid-cols-2">
              <fieldset className="space-y-2">
                <legend className="text-label font-semibold text-ink">Wind · kn</legend>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Ab"><Input type="number" min={0} max={80} step="any" inputMode="decimal" value={current.windMinKn ?? ""} disabled={busy} onChange={(event) => setCondition(active, "windMinKn", event.target.value)} /></Field>
                  <Field label="Bis"><Input type="number" min={0} max={80} step="any" inputMode="decimal" value={current.windMaxKn ?? ""} disabled={busy} onChange={(event) => setCondition(active, "windMaxKn", event.target.value)} /></Field>
                </div>
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-label font-semibold text-ink">Wellen · m</legend>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Ab"><Input type="number" min={0} max={12} step="any" inputMode="decimal" value={current.waveMinM ?? ""} disabled={busy} onChange={(event) => setCondition(active, "waveMinM", event.target.value)} /></Field>
                  <Field label="Bis"><Input type="number" min={0} max={12} step="any" inputMode="decimal" value={current.waveMaxM ?? ""} disabled={busy} onChange={(event) => setCondition(active, "waveMaxM", event.target.value)} /></Field>
                </div>
              </fieldset>
              <Field label="Wassertemperatur ab · °C"><Input type="number" min={-5} max={40} step="any" inputMode="decimal" value={current.waterTempMinC ?? ""} disabled={busy} onChange={(event) => setCondition(active, "waterTempMinC", event.target.value)} /></Field>
            </div>
          </div>}
          <p className="mt-3 text-caption text-muted">Leere Felder schränken deine Bedingungen nicht ein. Die Grenzwerte gibst du in kn, m und °C ein.</p>
        </div>}

        {invalid && <p role="alert" className="text-label text-danger">{invalid}</p>}
        {note && <p role={note.kind === "error" ? "alert" : "status"} className={`text-label font-medium ${note.kind === "error" ? "text-danger" : "text-success"}`}>{note.text}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={!dirty || Boolean(invalid) || busy}>{busy ? "Speichere …" : "Bedingungen speichern"}</Button>
          {dirty && <Button type="button" variant="ghost" onClick={reset} disabled={busy}>Verwerfen</Button>}
        </div>
      </form>
    </section>
  );
}
