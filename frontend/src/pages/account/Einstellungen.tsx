import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { usePrefs } from "../../context/PrefsContext";
import {
  updateProfile,
  requestEmailChange,
  updatePreferences,
  changePassword,
  deleteAccount,
  downloadAccountExport,
  AccountError,
} from "../../lib/account";
import {
  formatWind,
  formatWave,
  formatTemp,
  formatDistance,
  WIND_UNIT_LABELS,
  WAVE_UNIT_LABELS,
  TEMP_UNIT_LABELS,
  DISTANCE_UNIT_LABELS,
  type WindUnit,
  type WaveUnit,
  type TempUnit,
  type DistanceUnit,
} from "../../lib/units";
import { Button, Field, Input, Select } from "../../components/ui";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import SportConditionsSection from "./SportConditionsSection";
import { AccountPage } from "./AccountLayout";
import UnsavedChangesDialog from "../../components/admin/UnsavedChangesDialog";
import {
  useFormDirty,
  useUnsavedChangesGuard,
} from "../../lib/useUnsavedChangesGuard";

/**
 * Account settings, grouped into short mobile-first sections separated by
 * hairlines (the editorial rhythm of the spot Info page — no boxed cards). Each
 * section's primary action is obvious without hunting. Only genuinely stored
 * options render as working controls; areas without a backend yet are shown as
 * clearly-labelled "Geplant" notes so the information architecture is visible
 * without faking a switch.
 */
export default function Einstellungen() {
  const { blocker, markDirty, markClean, setDirty } = useUnsavedChangesGuard();
  const setProfileDirty = useCallback(
    (value: boolean) => (value ? markDirty("profile") : markClean("profile")),
    [markClean, markDirty]
  );
  const setPasswordDirty = useCallback(
    (value: boolean) => (value ? markDirty("password") : markClean("password")),
    [markClean, markDirty]
  );
  const setEmailDirty = useCallback(
    (value: boolean) => (value ? markDirty("email") : markClean("email")),
    [markClean, markDirty]
  );
  const setConditionsDirty = useCallback(
    (value: boolean) => (value ? markDirty("conditions") : markClean("conditions")),
    [markClean, markDirty]
  );
  return (
    <AccountPage title="Einstellungen">
      <div className="space-y-10">
        <SportConditionsSection onDirtyChange={setConditionsDirty} />
        <UnitsSection />
        <AccountSection onProfileDirty={setProfileDirty} onEmailDirty={setEmailDirty} onPasswordDirty={setPasswordDirty} />
        <PrivacySection onDirtyChange={(dirty) => setDirty("delete-account", dirty)} />
        <NotificationsSection />
      </div>
      <UnsavedChangesDialog blocker={blocker} />
    </AccountPage>
  );
}

// --- section chassis -------------------------------------------------------

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-line pt-8 first:border-t-0 first:pt-0">
      <h2 className="text-sz-18 font-semibold text-ink">{title}</h2>
      {description && <p className="mt-1 max-w-[60ch] text-ui text-muted">{description}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function PlannedNote({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-line px-4 py-4">
      <span className="inline-flex items-center rounded-full bg-band px-2.5 py-0.5 text-caption font-semibold uppercase tracking-wide text-muted">
        Geplant
      </span>
      <p className="mt-2 max-w-[60ch] text-ui text-muted">{children}</p>
    </div>
  );
}

function Note({ kind, children }: { kind: "ok" | "err"; children: ReactNode }) {
  return (
    <p
      role={kind === "err" ? "alert" : "status"}
      className={`text-label font-medium ${kind === "ok" ? "text-success" : "text-danger"}`}
    >
      {children}
    </p>
  );
}

// --- 2) Units & display (functional) ---------------------------------------

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
    <Field label={label}>
      <Select value={value} onChange={(e) => onChange(e.target.value as T)}>
        {(Object.entries(options) as [T, string][]).map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </Select>
    </Field>
  );
}

function UnitsSection() {
  const { units, setUnit, retrySave, saving, error } = usePrefs();
  return (
    <Section
      title="Einheiten & Anzeige"
      description="Deine Auswahl gilt überall auf der Seite, wo Wind, Wellenhöhe, Temperatur und Entfernungen angezeigt werden."
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <UnitSelect label="Wind" value={units.wind} onChange={(v: WindUnit) => setUnit("wind", v)} options={WIND_UNIT_LABELS} />
        <UnitSelect label="Wellenhöhe" value={units.wave} onChange={(v: WaveUnit) => setUnit("wave", v)} options={WAVE_UNIT_LABELS} />
        <UnitSelect label="Temperatur" value={units.temp} onChange={(v: TempUnit) => setUnit("temp", v)} options={TEMP_UNIT_LABELS} />
        <UnitSelect label="Entfernung" value={units.distance} onChange={(v: DistanceUnit) => setUnit("distance", v)} options={DISTANCE_UNIT_LABELS} />
      </div>
      <div className="mt-4 rounded-2xl bg-band px-4 py-3 text-label text-ink">
        Vorschau: Wind {formatWind(18, units.wind)} · Welle {formatWave(1.2, units.wave)} · Wasser{" "}
        {formatTemp(17, units.temp)} · Station {formatDistance(3.4, units.distance)}
      </div>
      {saving && <p role="status" className="mt-2 text-caption text-muted">Einheiten werden gespeichert …</p>}
      {error && <div role="alert" className="mt-2 text-caption text-danger">{error} <button type="button" onClick={retrySave} disabled={saving} className="min-h-11 font-semibold underline">Erneut versuchen</button></div>}
    </Section>
  );
}

// --- 3) Account (functional): profile + password ---------------------------

function AccountSection({
  onProfileDirty,
  onEmailDirty,
  onPasswordDirty,
}: {
  onProfileDirty: (dirty: boolean) => void;
  onEmailDirty: (dirty: boolean) => void;
  onPasswordDirty: (dirty: boolean) => void;
}) {
  return (
    <Section title="Konto" description="Deine persönlichen Angaben und dein Passwort.">
      <div className="space-y-8">
        <ProfileForm onDirtyChange={onProfileDirty} />
        <div className="border-t border-line pt-8"><EmailForm onDirtyChange={onEmailDirty} /></div>
        <div className="border-t border-line pt-8">
          <PasswordForm onDirtyChange={onPasswordDirty} />
        </div>
      </div>
    </Section>
  );
}

function ProfileForm({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.displayName ?? "");
  const [note, setNote] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    onDirtyChange(name !== (user?.displayName ?? ""));
  }, [name, onDirtyChange, user?.displayName]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNote(null);
    setBusy(true);
    try {
      const updated = await updateProfile({ displayName: name });
      setUser(updated);
      setNote({ kind: "ok", msg: "Profil gespeichert." });
    } catch (err) {
      setNote({ kind: "err", msg: err instanceof AccountError ? err.message : "Speichern fehlgeschlagen." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Field label="Anzeigename">
        <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="nickname" />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? "Speichere …" : "Speichern"}
        </Button>
        {note && <Note kind={note.kind}>{note.msg}</Note>}
      </div>
    </form>
  );
}

function EmailForm({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { user, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  useEffect(() => onDirtyChange(Boolean(email || password)), [email, password, onDirtyChange]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setNote(null);
    try {
      setUser(await requestEmailChange(email, password));
      setEmail(""); setPassword("");
      setNote({ kind: "ok", msg: "Bestätigungslink an die neue E-Mail-Adresse gesendet. Bis zur Bestätigung bleibt deine bisherige Adresse gültig." });
    } catch (err) {
      setNote({ kind: "err", msg: err instanceof AccountError ? err.message : "Adresswechsel fehlgeschlagen." });
    } finally { setBusy(false); }
  };
  return <form onSubmit={submit} className="space-y-4">
    <p className="text-label font-semibold uppercase tracking-wide text-muted">E-Mail-Adresse ändern</p>
    <p className="text-label text-muted">Aktuell: {user?.email}{user?.pendingEmail ? ` · Bestätigung ausstehend für ${user.pendingEmail}` : ""}</p>
    <Field label="Neue E-Mail-Adresse"><Input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
    <Field label="Aktuelles Passwort"><Input type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
    <div className="flex flex-wrap items-center gap-3"><Button type="submit" variant="secondary" disabled={busy || !email || !password}>{busy ? "Sende …" : "Bestätigungslink senden"}</Button>{note && <Note kind={note.kind}>{note.msg}</Note>}</div>
  </form>;
}

function PasswordForm({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
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
      setNote({ kind: "err", msg: err instanceof AccountError ? err.message : "Ändern fehlgeschlagen." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-label font-semibold uppercase tracking-wide text-muted">Passwort ändern</p>
      <Field label="Aktuelles Passwort">
        <Input type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} autoComplete="current-password" />
      </Field>
      <Field label="Neues Passwort" hint="Mindestens 8 Zeichen.">
        <Input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoComplete="new-password" />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="secondary" disabled={busy || !oldPw || !newPw}>
          {busy ? "Ändere …" : "Passwort ändern"}
        </Button>
        {note && <Note kind={note.kind}>{note.msg}</Note>}
      </div>
    </form>
  );
}

// --- 4) Privacy & content (planned visibility + functional data) -----------

function PrivacySection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [discardOpen, setDiscardOpen] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState("");
  const dirty = useFormDirty(password, "", open);

  const exportData = async () => {
    setExportBusy(true); setExportError("");
    try { await downloadAccountExport(); }
    catch (err) { setExportError(err instanceof AccountError ? err.message : "Datenexport fehlgeschlagen. Bitte versuche es erneut."); }
    finally { setExportBusy(false); }
  };

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
    <Section
      title="Privatsphäre & Inhalte"
      description="Steuere die Sichtbarkeit deines Profils und deiner Beiträge sowie deine Kontodaten."
    >
      <div className="space-y-6">
        <PlannedNote>
          Ein öffentliches Profil und die Sichtbarkeit einzelner Beiträge folgen,
          sobald diese Inhalte serverseitig gespeichert und moderiert werden. Dein
          Konto ist bis dahin privat — nur du siehst deine Favoriten und Vorschläge.
        </PlannedNote>

        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-muted">Deine Daten</p>
          <p className="mt-1 max-w-[60ch] text-ui text-muted">
            Lade eine Kopie deiner Kontodaten herunter oder lösche dein Konto endgültig.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <Button type="button" variant="secondary" disabled={exportBusy} onClick={() => void exportData()}>
              {exportBusy ? "Export wird erstellt …" : "Datenexport herunterladen"}
            </Button>
            <Button type="button" variant="danger" onClick={() => setOpen(true)}>
              Konto löschen
            </Button>
          </div>
          {exportError && <p role="alert" className="mt-2 text-label text-danger">{exportError}</p>}
        </div>
      </div>

      <Modal open={open} onClose={close} labelledBy="delete-account-title" describedBy="delete-account-description">
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
            <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
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
    </Section>
  );
}

// --- 5) Notifications (planned) --------------------------------------------

function NotificationsSection() {
  const { user, setUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const enabled = user?.preferences.submissionEmails ?? false;
  const toggle = async () => {
    setBusy(true); setError("");
    try { setUser(await updatePreferences({ submissionEmails: !enabled })); }
    catch (err) { setError(err instanceof AccountError ? err.message : "Einstellung konnte nicht gespeichert werden."); }
    finally { setBusy(false); }
  };
  return (
    <Section title="Benachrichtigungen" description="Wähle, welche Nachrichten du zu deinen Vorschlägen erhalten möchtest.">
      {!user?.mailAvailable ? <PlannedNote>E-Mail-Benachrichtigungen sind derzeit nicht verfügbar. Sobald der Versand eingerichtet ist, kannst du hier über Entscheidungen zu deinen Vorschlägen informiert werden.</PlannedNote> : <>
      <label className="inline-flex min-h-11 items-center gap-3 text-ui text-ink"><input type="checkbox" checked={enabled} disabled={busy} onChange={() => void toggle()} />E-Mail bei Entscheidung über meinen Spot-Vorschlag</label>
      {error && <p role="alert" className="mt-2 text-label text-danger">{error}</p>}
      </>}
      <p className="mt-2 text-caption text-muted">Wetteralarme für Favoriten folgen, sobald zuverlässige Schwellen und Versandzeiten feststehen.</p>
    </Section>
  );
}
