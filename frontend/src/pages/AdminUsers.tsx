// Admin-only user management (Sprint A): list, create, change role / active,
// reset password. Guards are enforced server-side; RequireAuth role="admin"
// keeps non-admins out of the route.

import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createAdminUser,
  confirmAdminMfa,
  deleteAdminUser,
  disableAdminMfa,
  getAdminUsers,
  getMe,
  setAdminUserPassword,
  resetAdminUserMfa,
  setupAdminMfa,
  updateAdminUser,
  type AdminUserRecord,
  type AuthUser,
} from "../lib/api";
import { roleLabel } from "../lib/labels";
import { Button, Input } from "../components/ui";
import PromptDialog from "../components/ui/PromptDialog";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import Modal from "../components/ui/Modal";
import { PageHeader, Badge } from "../components/admin/ui";
import { PlusIcon } from "../lib/icons";

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [me, setMe] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Password-reset + delete dialog targets (null = closed).
  const [pwTarget, setPwTarget] = useState<AdminUserRecord | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUserRecord | null>(null);
  // Edit dialog (email + display name).
  const [editTarget, setEditTarget] = useState<AdminUserRecord | null>(null);
  const [editEmail, setEditEmail] = useState("");
  const [editName, setEditName] = useState("");
  const [dialogBusy, setDialogBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createDirty, setCreateDirty] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [editDiscard, setEditDiscard] = useState(false);
  const [mfaOpen, setMfaOpen] = useState(false);
  const [mfaResetTarget, setMfaResetTarget] = useState<AdminUserRecord | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await getAdminUsers());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    getMe().then(setMe).catch(() => setMe(null));
  }, []);

  // Keep the online/offline dots live in the background — refetch presence
  // without the full-page "Lädt…" flash a normal load() would trigger.
  useEffect(() => {
    const id = setInterval(() => {
      getAdminUsers().then(setUsers).catch(() => {});
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 2500);
  };

  // Client-side mirrors of the server guards, for disabling the buttons up
  // front (the server stays authoritative).
  const activeAdminCount = users.filter(
    (u) => u.role === "admin" && u.is_active
  ).length;
  const isSelf = (u: AdminUserRecord) => me?.id === u.id;
  // Online = seen within the heartbeat window (backend refreshes last_seen_at on
  // every request, throttled to ~1/min). A deactivated account is never online.
  const isOnline = (u: AdminUserRecord) =>
    u.is_active &&
    !!u.last_seen_at &&
    Date.now() - new Date(u.last_seen_at).getTime() < 5 * 60 * 1000;
  const isLastActiveAdmin = (u: AdminUserRecord) =>
    u.role === "admin" && u.is_active && activeAdminCount <= 1;

  const onToggleActive = async (u: AdminUserRecord) => {
    try {
      await updateAdminUser(u.id, { is_active: !u.is_active });
      flash(`${u.email} ${u.is_active ? "deaktiviert" : "aktiviert"}.`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktualisierung fehlgeschlagen.");
    }
  };

  const onResetPassword = async (pw: string) => {
    if (!pwTarget) return;
    setDialogBusy(true);
    setError(null);
    try {
      await setAdminUserPassword(pwTarget.id, pw);
      flash(`Passwort für ${pwTarget.email} geändert.`);
      setPwTarget(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Passwort ändern fehlgeschlagen.");
    } finally {
      setDialogBusy(false);
    }
  };

  const onDelete = async () => {
    if (!deleteTarget) return;
    setDialogBusy(true);
    setError(null);
    try {
      await deleteAdminUser(deleteTarget.id);
      flash(`${deleteTarget.email} gelöscht.`);
      setDeleteTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen.");
    } finally {
      setDialogBusy(false);
    }
  };

  const openEdit = (u: AdminUserRecord) => {
    setEditTarget(u);
    setEditEmail(u.email);
    setEditName(u.display_name);
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setDialogBusy(true);
    setError(null);
    try {
      await updateAdminUser(editTarget.id, {
        email: editEmail.trim(),
        display_name: editName.trim(),
      });
      flash("Benutzer aktualisiert.");
      setEditTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen.");
    } finally {
      setDialogBusy(false);
    }
  };

  const requestCloseEdit = () => {
    if (!editTarget || dialogBusy) return;
    const dirty =
      editEmail !== editTarget.email || editName !== editTarget.display_name;
    if (dirty) setEditDiscard(true);
    else setEditTarget(null);
  };

  // Status badge + actions — shared by the desktop table and the mobile cards.
  const statusBadge = (u: AdminUserRecord) =>
    !u.is_active ? (
      <Badge tone="neutral">Deaktiviert</Badge>
    ) : isOnline(u) ? (
      <Badge tone="success">Online</Badge>
    ) : (
      <Badge tone="neutral">Offline</Badge>
    );

  const userActions = (u: AdminUserRecord) => (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onToggleActive(u)}
        disabled={isSelf(u) || isLastActiveAdmin(u)}
        title={
          isSelf(u)
            ? "Du kannst dich nicht selbst deaktivieren."
            : isLastActiveAdmin(u)
            ? "Der letzte aktive Admin kann nicht deaktiviert werden."
            : undefined
        }
        className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:cursor-not-allowed disabled:opacity-40"
      >
        {u.is_active ? "Deaktivieren" : "Aktivieren"}
      </button>
      <button
        type="button"
        onClick={() => openEdit(u)}
        className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
      >
        Bearbeiten
      </button>
      <button
        type="button"
        onClick={() => setPwTarget(u)}
        className="rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
      >
        Passwort
      </button>
      {u.mfa_enabled && !isSelf(u) && (
        <button
          type="button"
          onClick={() => setMfaResetTarget(u)}
          className="rounded-md border border-admin-warning-bg bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-warning transition-colors hover:bg-admin-warning-bg"
        >
          2FA zurücksetzen
        </button>
      )}
      <button
        type="button"
        onClick={() => setDeleteTarget(u)}
        disabled={isSelf(u) || isLastActiveAdmin(u)}
        title={
          isSelf(u)
            ? "Du kannst dein eigenes Konto nicht löschen."
            : isLastActiveAdmin(u)
            ? "Der letzte aktive Admin kann nicht gelöscht werden."
            : undefined
        }
        className="rounded-md border border-admin-danger-border bg-admin-surface px-2.5 py-1 text-label font-medium text-admin-danger transition-colors hover:bg-admin-danger-bg disabled:cursor-not-allowed disabled:opacity-40"
      >
        Löschen
      </button>
    </div>
  );

  return (
    <div>
      <PageHeader
        title="Benutzer"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setMfaOpen(true)}>
              2FA {me?.mfa_enabled ? "aktiv" : "einrichten"}
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <PlusIcon className="text-[16px]" /> Benutzer anlegen
            </Button>
          </div>
        }
      />

        {notice && (
          <div
            role="status"
            className="mt-4 rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label font-medium text-admin-success"
          >
            {notice}
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
          >
            {error}
          </div>
        )}

        <Modal
          open={createOpen}
          onClose={() => createDirty ? setConfirmDiscard(true) : setCreateOpen(false)}
          labelledBy="create-user-title"
        >
          <CreateUserForm
            onDirtyChange={setCreateDirty}
            onCancel={() => createDirty ? setConfirmDiscard(true) : setCreateOpen(false)}
            onCreated={async (email) => {
              setCreateDirty(false);
              setCreateOpen(false);
              flash(`Benutzer ${email} angelegt.`);
              await load();
            }}
            onError={setError}
          />
        </Modal>
        <ConfirmDialog
          open={confirmDiscard}
          title="Eingaben verwerfen?"
          message="Die noch nicht gespeicherten Benutzerdaten gehen verloren."
          confirmText="Verwerfen"
          onCancel={() => setConfirmDiscard(false)}
          onConfirm={() => {
            setConfirmDiscard(false);
            setCreateDirty(false);
            setCreateOpen(false);
          }}
        />
        <MfaModal
          open={mfaOpen}
          enabled={Boolean(me?.mfa_enabled)}
          onClose={() => setMfaOpen(false)}
          onChanged={async () => {
            setMe(await getMe());
            setMfaOpen(false);
            flash("Zwei-Faktor-Schutz aktualisiert.");
          }}
        />
        <ConfirmDialog
          open={mfaResetTarget !== null}
          title="2FA zurücksetzen"
          message={mfaResetTarget ? `${mfaResetTarget.email} muss 2FA anschließend neu einrichten.` : undefined}
          confirmText="Zurücksetzen"
          variant="danger"
          busy={dialogBusy}
          onCancel={() => setMfaResetTarget(null)}
          onConfirm={async () => {
            if (!mfaResetTarget) return;
            setDialogBusy(true);
            try {
              await resetAdminUserMfa(mfaResetTarget.id);
              flash(`2FA für ${mfaResetTarget.email} zurückgesetzt.`);
              setMfaResetTarget(null);
              await load();
            } catch (e) {
              setError(e instanceof ApiError ? e.message : "2FA-Reset fehlgeschlagen.");
            } finally {
              setDialogBusy(false);
            }
          }}
        />

        {/* Mobile / tablet: card list — all actions stay visible. */}
        <div className="mt-8 space-y-2 lg:hidden">
          {loading ? (
            <div className="rounded-lg border border-admin-border bg-admin-surface px-4 py-6 text-center text-admin-muted">
              Lädt…
            </div>
          ) : users.length === 0 ? (
            <div className="rounded-lg border border-dashed border-admin-border bg-admin-surface px-4 py-10 text-center text-admin-muted">
              Keine Benutzer.
            </div>
          ) : (
            users.map((u) => (
              <div
                key={u.id}
                className={`rounded-lg border border-admin-border bg-admin-surface p-4 ${
                  u.is_active ? "" : "opacity-60"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-admin-fg">{u.display_name}</div>
                    <div className="admin-mono truncate text-caption text-admin-muted">{u.email}</div>
                  </div>
                  {statusBadge(u)}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-label text-admin-fg2">
                  <span className="inline-flex items-center gap-2">
                    {roleLabel(u.role)}
                    {isSelf(u) && (
                      <Badge tone="primary" dot={false}>
                        du
                      </Badge>
                    )}
                  </span>
                  <span className="admin-mono text-admin-muted">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString("de-DE") : "—"}
                  </span>
                </div>
                <div className="mt-3">{userActions(u)}</div>
              </div>
            ))
          )}
        </div>

        {/* Desktop: dense table. */}
        <div className="mt-8 hidden overflow-x-auto rounded-lg border border-admin-border bg-admin-surface lg:block">
          <table className="w-full min-w-[720px] text-left text-ui">
            <thead className="border-b border-admin-border bg-admin-hover text-caption uppercase tracking-wide text-admin-muted">
              <tr>
                <th className="px-4 py-2.5 font-semibold">E-Mail</th>
                <th className="px-4 py-2.5 font-semibold">Name</th>
                <th className="px-4 py-2.5 font-semibold">Rolle</th>
                <th className="px-4 py-2.5 font-semibold">Status</th>
                <th className="px-4 py-2.5 font-semibold">Letzter Login</th>
                <th className="px-4 py-2.5 font-semibold">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-admin-border-subtle">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-admin-muted">
                    Lädt…
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-admin-muted">
                    Keine Benutzer.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr
                    key={u.id}
                    className={`transition-colors hover:bg-admin-hover ${
                      u.is_active ? "" : "opacity-60"
                    }`}
                  >
                    <td className="admin-mono px-4 py-3 text-admin-fg">{u.email}</td>
                    <td className="px-4 py-3 text-admin-fg">{u.display_name}</td>
                    <td className="px-4 py-3 text-label text-admin-fg2">
                      <span className="inline-flex items-center gap-2">
                        {roleLabel(u.role)}
                        {isSelf(u) && (
                          <Badge tone="primary" dot={false}>
                            du
                          </Badge>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3">{statusBadge(u)}</td>
                    <td className="admin-mono px-4 py-3 text-label text-admin-muted">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleString("de-DE")
                        : "—"}
                    </td>
                    <td className="px-4 py-3">{userActions(u)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <Modal
          open={editTarget !== null}
          onClose={requestCloseEdit}
          labelledBy="edit-user-title"
        >
          <h2 id="edit-user-title" className="text-ui font-semibold text-ink">
            Benutzer bearbeiten
          </h2>
          <label htmlFor="edit-user-email" className="mt-3 block text-label text-ink-soft">E-Mail</label>
          <Input
            id="edit-user-email"
            type="email"
            value={editEmail}
            onChange={(e) => setEditEmail(e.target.value)}
            className="mt-1"
          />
          <label htmlFor="edit-user-name" className="mt-3 block text-label text-ink-soft">Anzeigename</label>
          <Input
            id="edit-user-name"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="mt-1"
          />
          <div className="mt-5 flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={requestCloseEdit} disabled={dialogBusy}>
              Abbrechen
            </Button>
            <Button
              onClick={saveEdit}
              disabled={dialogBusy || !editEmail.trim() || !editName.trim()}
            >
              {dialogBusy ? "…" : "Speichern"}
            </Button>
          </div>
        </Modal>
        <ConfirmDialog
          open={editDiscard}
          title="Änderungen verwerfen?"
          message="E-Mail oder Anzeigename wurden noch nicht gespeichert."
          confirmText="Verwerfen"
          variant="danger"
          onCancel={() => setEditDiscard(false)}
          onConfirm={() => {
            setEditDiscard(false);
            setEditTarget(null);
          }}
        />

        <PromptDialog
          open={pwTarget !== null}
          title="Passwort zurücksetzen"
          label={pwTarget ? `Neues Passwort für ${pwTarget.email}` : undefined}
          type="password"
          confirmText="Passwort setzen"
          busy={dialogBusy}
          onConfirm={onResetPassword}
          onCancel={() => setPwTarget(null)}
        />
        <ConfirmDialog
          open={deleteTarget !== null}
          title="Benutzer löschen"
          message={
            deleteTarget
              ? `${deleteTarget.email} wird dauerhaft gelöscht. Das lässt sich nicht rückgängig machen.`
              : undefined
          }
          busy={dialogBusy}
          onConfirm={onDelete}
          onCancel={() => setDeleteTarget(null)}
        />
    </div>
  );
}

function CreateUserForm({
  onCreated,
  onError,
  onCancel,
  onDirtyChange,
}: {
  onCreated: (email: string) => void | Promise<void>;
  onError: (msg: string) => void;
  onCancel: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      // Role is fixed to admin server-side — no picker.
      await createAdminUser({
        email: email.trim(),
        password,
        display_name: displayName.trim() || undefined,
      });
      setEmail("");
      setDisplayName("");
      setPassword("");
      onDirtyChange(false);
      await onCreated(email.trim());
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <h2 id="create-user-title" className="text-[18px] font-semibold text-admin-fg">
        Benutzer anlegen
      </h2>
      <p className="rounded-md border border-admin-info-bg bg-admin-info-bg px-3 py-2 text-label text-admin-info">
        Neue Benutzer erhalten Zugriff auf das Dashboard. Das Passwort muss mindestens 12 Zeichen lang sein.
      </p>
      <div>
        <label htmlFor="create-user-email" className="text-label font-medium text-admin-fg">E-Mail</label>
        <Input
          id="create-user-email"
          type="email"
          className="mt-1 w-full"
          autoComplete="off"
          value={email}
          onChange={(e) => { setEmail(e.target.value); onDirtyChange(true); }}
          required
        />
      </div>
      <div>
        <label htmlFor="create-user-name" className="text-label font-medium text-admin-fg">Anzeigename</label>
        <Input
          id="create-user-name"
          type="text"
          className="mt-1 w-full"
          value={displayName}
          onChange={(e) => { setDisplayName(e.target.value); onDirtyChange(true); }}
        />
      </div>
      <div>
        <label htmlFor="create-user-password" className="text-label font-medium text-admin-fg">Passwort</label>
        <Input
          id="create-user-password"
          type="password"
          className="mt-1 w-full"
          autoComplete="new-password"
          minLength={12}
          value={password}
          onChange={(e) => { setPassword(e.target.value); onDirtyChange(true); }}
          required
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>
          Abbrechen
        </Button>
        <Button type="submit" disabled={busy || !email || password.length < 12}>
          {busy ? "…" : "Anlegen"}
        </Button>
      </div>
    </form>
  );
}

function MfaModal({
  open,
  enabled,
  onClose,
  onChanged,
}: {
  open: boolean;
  enabled: boolean;
  onClose: () => void;
  onChanged: () => void | Promise<void>;
}) {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [discardOpen, setDiscardOpen] = useState(false);

  useEffect(() => {
    if (open) {
      setPassword("");
      setCode("");
      setSecret("");
      setError("");
      setDiscardOpen(false);
    }
  }, [open]);

  const requestClose = () => {
    if (busy) return;
    if (password || code || secret) setDiscardOpen(true);
    else onClose();
  };

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await setupAdminMfa(password);
      setSecret(result.secret);
      setPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Einrichtung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    setError("");
    try {
      await confirmAdminMfa(code);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Code konnte nicht bestätigt werden.");
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    setError("");
    try {
      await disableAdminMfa(password, code);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "2FA konnte nicht deaktiviert werden.");
    } finally {
      setBusy(false);
    }
  };

  const codeField = (
    <div>
      <label htmlFor="mfa-code" className="text-label font-medium text-admin-fg">
        Sechsstelliger Code
      </label>
      <Input
        id="mfa-code"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={code}
        onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
        className="mt-1 w-full"
      />
    </div>
  );

  return (
    <>
      <Modal open={open} onClose={requestClose} labelledBy="mfa-title">
        <div className="space-y-4">
          <h2 id="mfa-title" className="text-[18px] font-semibold text-admin-fg">
            Zwei-Faktor-Schutz
          </h2>
          {enabled ? (
            <>
              <p className="text-label text-admin-muted">
                Zum Deaktivieren sind Passwort und aktueller Authenticator-Code erforderlich.
              </p>
              <div>
                <label htmlFor="mfa-password" className="text-label font-medium text-admin-fg">Passwort</label>
                <Input id="mfa-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 w-full" />
              </div>
              {codeField}
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={requestClose} disabled={busy}>Abbrechen</Button>
                <Button variant="danger" onClick={disable} disabled={busy || !password || code.length !== 6}>2FA deaktivieren</Button>
              </div>
            </>
          ) : secret ? (
            <>
              <p className="text-label text-admin-muted">
                Hinterlege dieses Secret in deiner Authenticator-App und bestätige den ersten Code.
              </p>
              <code className="block break-all rounded-md border border-admin-border bg-admin-bg p-3 text-label text-admin-fg" aria-label="TOTP Secret">{secret}</code>
              {codeField}
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={requestClose} disabled={busy}>Abbrechen</Button>
                <Button onClick={finish} disabled={busy || code.length !== 6}>Aktivieren</Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-label text-admin-muted">
                Bestätige zuerst dein Passwort. Danach wird das einmalig sichtbare Secret erzeugt.
              </p>
              <div>
                <label htmlFor="mfa-password" className="text-label font-medium text-admin-fg">Passwort</label>
                <Input id="mfa-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 w-full" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={requestClose} disabled={busy}>Abbrechen</Button>
                <Button onClick={start} disabled={busy || !password}>Einrichtung starten</Button>
              </div>
            </>
          )}
          {error && <p role="alert" className="text-label text-admin-danger">{error}</p>}
        </div>
      </Modal>
      <ConfirmDialog
        open={discardOpen}
        title="2FA-Einrichtung verlassen?"
        message="Nicht bestätigte Eingaben und das angezeigte Secret werden verworfen."
        confirmText="Verwerfen"
        variant="danger"
        onCancel={() => setDiscardOpen(false)}
        onConfirm={() => {
          setDiscardOpen(false);
          onClose();
        }}
      />
    </>
  );
}
