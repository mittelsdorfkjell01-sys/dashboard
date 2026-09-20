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
  return (
    <>
      <div className="space-y-10">
        <SportsSection />
        <UnitsSection />
        <AccountSection onProfileDirty={setProfileDirty} onPasswordDirty={setPasswordDirty} />
        <PrivacySection onDirtyChange={(dirty) => setDirty("delete-account", dirty)} />
        <NotificationsSection />
      </div>
      <UnsavedChangesDialog blocker={blocker} />
    </>
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

// --- 1) Sports & conditions (planned) --------------------------------------

function SportsSection() {
  return (
    <Section
      title="Sportarten & Bedingungen"
      description="Wähle deine Disziplinen und Wunschbedingungen, damit die Seite Spots und Zeiten auf dich zuschneidet."
    >
      <PlannedNote>
        Unterstützt sind Surfen, Windsurfen, Kitesurfen und Wingfoilen. Persönliche
        Sportarten und bevorzugte Bedingungen lassen sich einstellen, sobald sie
        serverseitig zu deinem Konto gespeichert werden — bis dahin bleibt diese
        Auswahl bewusst leer statt eines Schalters ohne Wirkung.
      </PlannedNote>
    </Section>
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
  const { units, setUnit } = usePrefs();
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
    </Section>
  );
}

// --- 3) Account (functional): profile + password ---------------------------

function AccountSection({
  onProfileDirty,
  onPasswordDirty,
}: {
  onProfileDirty: (dirty: boolean) => void;
  onPasswordDirty: (dirty: boolean) => void;
}) {
  return (
    <Section title="Konto" description="Deine persönlichen Angaben und dein Passwort.">
      <div className="space-y-8">
        <ProfileForm onDirtyChange={onProfileDirty} />
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
      <Field label="E-Mail">
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
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
      <Field label="Neues Passwort" hint="Mindestens 12 Zeichen.">
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
            <Button type="button" variant="secondary" onClick={() => void downloadAccountExport()}>
              Datenexport herunterladen
            </Button>
            <Button type="button" variant="danger" onClick={() => setOpen(true)}>
              Konto löschen
            </Button>
          </div>
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
  return (
    <Section title="Benachrichtigungen" description="Werde informiert, wenn an deinen Spots gute Bedingungen erwartet werden.">
      <PlannedNote>
        Benachrichtigungen erscheinen hier, sobald ein Versandkanal (E-Mail oder
        Push) angebunden ist. Es werden nur Kanäle und Ereignisse angeboten, die
        tatsächlich verfügbar sind.
      </PlannedNote>
    </Section>
  );
}
