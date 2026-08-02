// Admin-only user management (Sprint A): list, create, change role / active,
// reset password. Guards are enforced server-side; RequireAuth role="admin"
// keeps non-admins out of the route.

import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createAdminUser,
  deleteAdminUser,
  getActivity,
  getAdminUsers,
  getMe,
  setAdminUserPassword,
  updateAdminUser,
  type ActivityItem,
  type AdminUserRecord,
  type AuthUser,
} from "../lib/api";
import { gapLabel, roleLabel } from "../lib/labels";
import { Button, Input } from "../components/ui";
import PromptDialog from "../components/ui/PromptDialog";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import Modal from "../components/ui/Modal";
import ActivityPreview from "../components/admin/ActivityPreview";
import { PageHeader, Badge } from "../components/admin/ui";

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

  return (
    <div>
      <PageHeader
        title="Benutzerverwaltung"
        description="Alle Operatoren haben volle Admin-Rechte. Du kannst dein eigenes Konto und den letzten aktiven Admin nicht deaktivieren oder löschen."
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

        <CreateUserForm
          onCreated={async (email) => {
            flash(`Benutzer ${email} angelegt.`);
            await load();
          }}
          onError={setError}
        />

        <div className="mt-8 overflow-x-auto rounded-lg border border-admin-border bg-admin-surface">
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
                    <td className="px-4 py-3">
                      {!u.is_active ? (
                        <Badge tone="neutral">Deaktiviert</Badge>
                      ) : isOnline(u) ? (
                        <Badge tone="success">Online</Badge>
                      ) : (
                        <Badge tone="neutral">Offline</Badge>
                      )}
                    </td>
                    <td className="admin-mono px-4 py-3 text-label text-admin-muted">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleString("de-DE")
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
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
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <ActivityLog />

        <Modal
          open={editTarget !== null}
          onClose={() => setEditTarget(null)}
          labelledBy="edit-user-title"
        >
          <h2 id="edit-user-title" className="text-ui font-semibold text-ink">
            Benutzer bearbeiten
          </h2>
          <label className="mt-3 block text-label text-ink-soft">E-Mail</label>
          <Input
            type="email"
            value={editEmail}
            onChange={(e) => setEditEmail(e.target.value)}
            className="mt-1"
          />
          <label className="mt-3 block text-label text-ink-soft">Anzeigename</label>
          <Input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="mt-1"
          />
          <div className="mt-5 flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditTarget(null)} disabled={dialogBusy}>
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

function ActivityLog() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [q, setQ] = useState("");
  const [preview, setPreview] = useState<ActivityItem | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      getActivity(q.trim() || undefined)
        .then(setItems)
        .catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <section className="mt-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-admin-fg">Aktivität</h2>
        <Input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Suche: Name, Spot …"
          className="max-w-[240px]"
        />
      </div>
      <p className="mt-1 text-label text-admin-muted">
        Letzte Änderungen durch das Team — pro Spot zusammengefasst (ein Eintrag
        je Spot, nicht je Aktion).
      </p>
      <ul className="mt-3 divide-y divide-admin-border-subtle rounded-lg border border-admin-border bg-admin-surface">
        {items.length === 0 ? (
          <li className="px-4 py-4 text-center text-label text-admin-muted">
            Noch keine Aktivität.
          </li>
        ) : (
          items.map((a, i) => {
            const clickable = a.kind === "spot" && !!a.target_id;
            const content = (
              <>
                <span className="min-w-0 text-ink">
                  <span className="font-medium">{a.actor ?? "—"}</span>{" "}
                  <span className="text-muted">{a.label}</span>
                  {a.target && <span className="text-ink"> — {a.target}</span>}
                  {a.fields.length > 0 && (
                    <span className="text-muted"> ({a.fields.map(gapLabel).join(", ")})</span>
                  )}
                  {a.actions && a.actions > 1 && (
                    <span className="text-caption text-muted"> · {a.actions} Änderungen</span>
                  )}
                </span>
                <span className="admin-mono shrink-0 text-caption text-admin-muted">
                  {a.at ? new Date(a.at).toLocaleString("de-DE") : ""}
                </span>
              </>
            );
            return (
              <li key={i}>
                {clickable ? (
                  <button
                    type="button"
                    onClick={() => setPreview(a)}
                    className="flex w-full items-start justify-between gap-3 px-4 py-2.5 text-left text-ui transition-colors hover:bg-admin-hover"
                  >
                    {content}
                  </button>
                ) : (
                  <div className="flex items-start justify-between gap-3 px-4 py-2.5 text-ui">
                    {content}
                  </div>
                )}
              </li>
            );
          })
        )}
      </ul>

      <ActivityPreview item={preview} onClose={() => setPreview(null)} />
    </section>
  );
}

function CreateUserForm({
  onCreated,
  onError,
}: {
  onCreated: (email: string) => void | Promise<void>;
  onError: (msg: string) => void;
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
      await onCreated(email.trim());
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="mt-6 rounded-lg border border-admin-border bg-admin-hover p-4 sm:p-5"
      noValidate
    >
      <p className="text-ui font-semibold text-admin-fg">Neuen Admin anlegen</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          type="email"
          placeholder="E-Mail"
          autoComplete="off"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          type="text"
          placeholder="Anzeigename (optional)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <Input
          type="password"
          placeholder="Passwort"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Button type="submit" disabled={busy || !email || !password} className="shrink-0">
          {busy ? "…" : "Anlegen"}
        </Button>
      </div>
    </form>
  );
}
