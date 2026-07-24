// Admin-only user management (Sprint A): list, create, change role / active,
// reset password. Guards are enforced server-side; RequireAuth role="admin"
// keeps non-admins out of the route.

import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createAdminUser,
  createTeamNote,
  deleteTeamNote,
  getActivity,
  getAdminUsers,
  getTeamNotes,
  setAdminUserPassword,
  updateAdminUser,
  type ActivityItem,
  type AdminRole,
  type AdminUserRecord,
  type TeamNote,
} from "../lib/api";
import { ROLE_LABELS, gapLabel, roleLabel } from "../lib/labels";
import { Button, Input, Select } from "../components/ui";

const ROLES: AdminRole[] = ["admin", "curator"];

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
  }, []);

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 2500);
  };

  const onRoleChange = async (u: AdminUserRecord, role: AdminRole) => {
    try {
      await updateAdminUser(u.id, { role });
      flash(`Rolle von ${u.email} auf ${roleLabel(role)} gesetzt.`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktualisierung fehlgeschlagen.");
    }
  };

  const onToggleActive = async (u: AdminUserRecord) => {
    try {
      await updateAdminUser(u.id, { is_active: !u.is_active });
      flash(`${u.email} ${u.is_active ? "deaktiviert" : "aktiviert"}.`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktualisierung fehlgeschlagen.");
    }
  };

  const onResetPassword = async (u: AdminUserRecord) => {
    const pw = window.prompt(`Neues Passwort für ${u.email}:`);
    if (!pw) return;
    try {
      await setAdminUserPassword(u.id, pw);
      flash(`Passwort für ${u.email} geändert.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Passwort ändern fehlgeschlagen.");
    }
  };

  return (
    <div>
      <h1 className="text-[24px] font-semibold text-ink">Benutzerverwaltung</h1>
        <p className="mt-2 text-[15px] text-muted">
          Admins verwalten alles; Moderatoren kuratieren und moderieren, ohne
          Zugriff auf die Benutzerverwaltung.
        </p>

        {notice && (
          <div
            role="status"
            className="mt-4 rounded-xl bg-green/10 px-3 py-2 text-[13px] font-medium text-green"
          >
            {notice}
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-[13px] font-medium text-red-700"
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

        <div className="mt-8 overflow-x-auto rounded-2xl border border-line">
          <table className="w-full min-w-[720px] text-left text-[14px]">
            <thead className="bg-ink/5 text-[12px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">E-Mail</th>
                <th className="px-4 py-3 font-semibold">Name</th>
                <th className="px-4 py-3 font-semibold">Rolle</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Letzter Login</th>
                <th className="px-4 py-3 font-semibold">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted">
                    Lädt…
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted">
                    Keine Benutzer.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className={u.is_active ? "" : "opacity-60"}>
                    <td className="px-4 py-3 text-ink">{u.email}</td>
                    <td className="px-4 py-3 text-ink">{u.display_name}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) =>
                          onRoleChange(u, e.target.value as AdminRole)
                        }
                        className="rounded-lg border border-line bg-white px-2 py-1 text-[13px] text-ink"
                        aria-label={`Rolle von ${u.email}`}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${
                          u.is_active ? "text-green" : "text-muted"
                        }`}
                      >
                        {u.is_active ? "● Aktiv" : "○ Inaktiv"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[13px] text-muted">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleString("de-DE")
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => onToggleActive(u)}
                          className="rounded-lg border border-teal/30 px-2.5 py-1 text-[13px] font-medium text-teal hover:bg-teal/5"
                        >
                          {u.is_active ? "Deaktivieren" : "Aktivieren"}
                        </button>
                        <button
                          type="button"
                          onClick={() => onResetPassword(u)}
                          className="rounded-lg border border-teal/30 px-2.5 py-1 text-[13px] font-medium text-teal hover:bg-teal/5"
                        >
                          Passwort
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <TeamBoard />
        <ActivityLog />
    </div>
  );
}

function TeamBoard() {
  const [notes, setNotes] = useState<TeamNote[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => getTeamNotes().then(setNotes).catch(() => {});
  useEffect(() => {
    void load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createTeamNote(body.trim());
      setBody("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await deleteTeamNote(id).catch(() => {});
    await load();
  };

  return (
    <section className="mt-10">
      <h2 className="text-[18px] font-semibold text-ink">Team-Notizen</h2>
      <p className="mt-1 text-[13px] text-muted">
        Nachrichten fürs Team — erscheinen als Kacheln auf der Übersicht.
      </p>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <Input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Nachricht fürs Team…"
        />
        <Button type="submit" disabled={busy || !body.trim()} className="shrink-0">
          Posten
        </Button>
      </form>
      {error && <p className="mt-2 text-[13px] text-red-600">{error}</p>}
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {notes.map((n) => (
          <div key={n.id} className="flex items-start justify-between gap-2 rounded-xl border border-line bg-teal/5 p-3">
            <div className="min-w-0">
              <p className="whitespace-pre-wrap text-[14px] text-ink">{n.body}</p>
              <p className="mt-1 text-[12px] text-muted">
                {n.author ?? "—"} · {new Date(n.created_at).toLocaleString("de-DE")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => remove(n.id)}
              className="shrink-0 text-[12px] text-muted hover:text-red-600"
              aria-label="Notiz löschen"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function ActivityLog() {
  const [items, setItems] = useState<ActivityItem[]>([]);

  useEffect(() => {
    getActivity().then(setItems).catch(() => {});
  }, []);

  return (
    <section className="mt-10">
      <h2 className="text-[18px] font-semibold text-ink">Aktivität</h2>
      <p className="mt-1 text-[13px] text-muted">
        Letzte echten Änderungen durch das Team (keine Klicks, nur Aktionen).
      </p>
      <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-white">
        {items.length === 0 ? (
          <li className="px-4 py-4 text-center text-[13px] text-muted">
            Noch keine Aktivität.
          </li>
        ) : (
          items.map((a, i) => (
            <li key={i} className="flex items-start justify-between gap-3 px-4 py-2.5 text-[14px]">
              <span className="min-w-0 text-ink">
                <span className="font-medium">{a.actor ?? "—"}</span>{" "}
                <span className="text-muted">{a.label}</span>
                {a.target && <span className="text-ink"> — {a.target}</span>}
                {a.fields.length > 0 && (
                  <span className="text-muted"> ({a.fields.map(gapLabel).join(", ")})</span>
                )}
              </span>
              <span className="shrink-0 text-[12px] text-muted">
                {a.at ? new Date(a.at).toLocaleString("de-DE") : ""}
              </span>
            </li>
          ))
        )}
      </ul>
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
  const [role, setRole] = useState<AdminRole>("curator");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await createAdminUser({
        email: email.trim(),
        password,
        display_name: displayName.trim() || undefined,
        role,
      });
      setEmail("");
      setDisplayName("");
      setPassword("");
      setRole("curator");
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
      className="mt-6 rounded-2xl bg-ink/5 p-4 sm:p-5"
      noValidate
    >
      <p className="text-[14px] font-semibold text-ink">Neuen Benutzer anlegen</p>
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
        <div className="flex gap-2">
          <Select
            value={role}
            onChange={(e) => setRole(e.target.value as AdminRole)}
            aria-label="Rolle"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </Select>
          <Button type="submit" disabled={busy || !email || !password} className="shrink-0">
            {busy ? "…" : "Anlegen"}
          </Button>
        </div>
      </div>
    </form>
  );
}
