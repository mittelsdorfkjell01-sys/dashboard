import { useState, type FormEvent, type ReactNode } from "react";
import { useAuth } from "../../context/AuthContext";
import { usePrefs } from "../../context/PrefsContext";
import { updateProfile, changePassword, AccountError } from "../../lib/account";
import {
  formatWind,
  formatWave,
  formatTemp,
  WIND_UNIT_LABELS,
  WAVE_UNIT_LABELS,
  TEMP_UNIT_LABELS,
  type WindUnit,
  type WaveUnit,
  type TempUnit,
} from "../../lib/units";
import { Button, Field, Input, fieldClass } from "../../components/ui";

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-card sm:p-6">
      <h2 className="mb-4 text-[16px] font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

function Note({ kind, children }: { kind: "ok" | "err"; children: ReactNode }) {
  return (
    <p
      role={kind === "err" ? "alert" : "status"}
      className={`mt-3 text-[13px] font-medium ${
        kind === "ok" ? "text-green-700" : "text-red-600"
      }`}
    >
      {children}
    </p>
  );
}

export default function Einstellungen() {
  return (
    <div className="space-y-6">
      <ProfileSection />
      <PasswordSection />
      <UnitsSection />
    </div>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.displayName ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [note, setNote] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNote(null);
    setBusy(true);
    try {
      const updated = await updateProfile({ displayName: name, email });
      setUser(updated);
      setNote({ kind: "ok", msg: "Profil gespeichert." });
    } catch (err) {
      setNote({
        kind: "err",
        msg: err instanceof AccountError ? err.message : "Speichern fehlgeschlagen.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Profilangaben">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Anzeigename">
          <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="nickname" />
        </Field>
        <Field label="E-Mail">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </Field>
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={busy}>
            {busy ? "Speichere …" : "Speichern"}
          </Button>
          {note && <Note kind={note.kind}>{note.msg}</Note>}
        </div>
      </form>
    </Panel>
  );
}

function PasswordSection() {
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [note, setNote] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNote(null);
    setBusy(true);
    try {
      await changePassword(oldPw, newPw);
      setOldPw("");
      setNewPw("");
      setNote({ kind: "ok", msg: "Passwort geändert." });
    } catch (err) {
      setNote({
        kind: "err",
        msg: err instanceof AccountError ? err.message : "Ändern fehlgeschlagen.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Passwort ändern">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Aktuelles Passwort">
          <Input
            type="password"
            value={oldPw}
            onChange={(e) => setOldPw(e.target.value)}
            autoComplete="current-password"
          />
        </Field>
        <Field label="Neues Passwort" hint="Mindestens 6 Zeichen.">
          <Input
            type="password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            autoComplete="new-password"
          />
        </Field>
        <div className="flex items-center gap-3">
          <Button type="submit" variant="secondary" disabled={busy || !oldPw || !newPw}>
            {busy ? "Ändere …" : "Passwort ändern"}
          </Button>
          {note && <Note kind={note.kind}>{note.msg}</Note>}
        </div>
      </form>
    </Panel>
  );
}

function UnitSelect<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: Record<T, string>;
}) {
  return (
    <label className="block">
      <span className="text-[13px] font-medium text-ink">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className={`${fieldClass} mt-1.5`}
      >
        {(Object.entries(options) as [T, string][]).map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}

function UnitsSection() {
  const { units, setUnit } = usePrefs();
  return (
    <Panel title="Einheiten">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <UnitSelect
          label="Wind"
          value={units.wind}
          onChange={(v: WindUnit) => setUnit("wind", v)}
          options={WIND_UNIT_LABELS}
        />
        <UnitSelect
          label="Wellenhöhe"
          value={units.wave}
          onChange={(v: WaveUnit) => setUnit("wave", v)}
          options={WAVE_UNIT_LABELS}
        />
        <UnitSelect
          label="Temperatur"
          value={units.temp}
          onChange={(v: TempUnit) => setUnit("temp", v)}
          options={TEMP_UNIT_LABELS}
        />
      </div>
      <div className="mt-4 rounded-xl bg-band px-4 py-3 text-[13px] text-ink">
        Vorschau: Wind {formatWind(18, units.wind)} · Welle {formatWave(1.2, units.wave)} ·
        Wasser {formatTemp(17, units.temp)}
      </div>
    </Panel>
  );
}
