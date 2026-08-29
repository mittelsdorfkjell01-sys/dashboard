import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { usePrefs } from "../../context/PrefsContext";
import {
  updateProfile,
  changePassword,
  deleteAccount,
  downloadAccountExport,
  AccountError,
} from "../../lib/account";
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
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import UnsavedChangesDialog from "../../components/admin/UnsavedChangesDialog";
import {
  useFormDirty,
  useUnsavedChangesGuard,
} from "../../lib/useUnsavedChangesGuard";

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <h2 className="mb-4 text-sz-16 font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

function Note({ kind, children }: { kind: "ok" | "err"; children: ReactNode }) {
  return (
    <p
      role={kind === "err" ? "alert" : "status"}
      className={`mt-3 text-label font-medium ${
        kind === "ok" ? "text-success" : "text-danger"
      }`}
    >
      {children}
    </p>
  );
}

export default function Einstellungen() {
  const { blocker, markDirty, markClean, setDirty } = useUnsavedChangesGuard();
  const setProfileDirty = useCallback(
    (value: boolean) => value ? markDirty("profile") : markClean("profile"),
    [markClean, markDirty]
  );
  const setPasswordDirty = useCallback(
    (value: boolean) => value ? markDirty("password") : markClean("password"),
    [markClean, markDirty]
  );
  return (
    <>
    <div className="space-y-6">
      <ProfileSection onDirtyChange={setProfileDirty} />
      <PasswordSection onDirtyChange={setPasswordDirty} />
      <UnitsSection />
      <PrivacySection onDirtyChange={(dirty) => setDirty("delete-account", dirty)} />
    </div>
    <UnsavedChangesDialog blocker={blocker} />
    </>
  );
}

function ProfileSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.displayName ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [note, setNote] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    onDirtyChange(name !== (user?.displayName ?? "") || email !== (user?.email ?? ""));
  }, [email, name, onDirtyChange, user?.displayName, user?.email]);

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

function PasswordSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [note, setNote] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    onDirtyChange(Boolean(oldPw || newPw));
  }, [newPw, oldPw, onDirtyChange]);

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
        <Field label="Neues Passwort" hint="Mindestens 12 Zeichen.">
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

function PrivacySection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [discardOpen, setDiscardOpen] = useState(false);
  const dirty = useFormDirty(password, "", open);

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  const close = () => {
    if (busy) return;
    if (dirty) setDiscardOpen(true);
    else setOpen(false);
  };

  const remove = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await deleteAccount(password);
      setUser(null);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Konto konnte nicht gelöscht werden.");
      setBusy(false);
    }
  };

  return (
    <Panel title="Daten & Konto">
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="secondary" onClick={() => void downloadAccountExport()}>
          Datenexport herunterladen
        </Button>
        <Button type="button" variant="danger" onClick={() => setOpen(true)}>
          Konto löschen
        </Button>
      </div>
      <Modal
        open={open}
        onClose={close}
        labelledBy="delete-account-title"
        describedBy="delete-account-description"
      >
        <form onSubmit={remove} className="space-y-4">
          <div>
            <h2 id="delete-account-title" className="text-sz-18 font-semibold text-ink">
              Konto endgültig löschen
            </h2>
            <p id="delete-account-description" className="mt-2 text-ui text-muted">
              Favoriten werden gelöscht. Veröffentlichte Beiträge bleiben anonymisiert erhalten.
            </p>
          </div>
          <Field label="Passwort zur Bestätigung">
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </Field>
          {error && <p role="alert" className="text-label text-danger">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={close} disabled={busy}>
              Abbrechen
            </Button>
            <Button type="submit" variant="danger" disabled={busy || !password}>
              {busy ? "Lösche …" : "Endgültig löschen"}
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={discardOpen}
        title="Löschung abbrechen?"
        message="Das eingegebene Passwort wird verworfen."
        confirmText="Verwerfen"
        variant="danger"
        onCancel={() => setDiscardOpen(false)}
        onConfirm={() => {
          setDiscardOpen(false);
          setPassword("");
          setOpen(false);
        }}
      />
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
      <span className="text-label font-medium text-ink">{label}</span>
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
      <div className="mt-4 rounded-xl bg-band px-4 py-3 text-label text-ink">
        Vorschau: Wind {formatWind(18, units.wind)} · Welle {formatWave(1.2, units.wave)} ·
        Wasser {formatTemp(17, units.temp)}
      </div>
    </Panel>
  );
}
