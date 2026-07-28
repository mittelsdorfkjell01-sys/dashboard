// Admin sign-in. On success, redirects to the page the user came from (via
// RequireAuth's location state) or the dashboard.

import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { Wordmark } from "../components/ui";

export default function AdminLogin() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from || "/admin";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already signed in → skip the form.
  if (user) {
    return <Navigate to={from} replace />;
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Anmeldung fehlgeschlagen. Bitte erneut versuchen."
      );
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    "w-full rounded-lg border border-line bg-white px-3 py-2.5 text-ui text-ink outline-none focus:border-teal/50";

  return (
    <div className="grid min-h-screen place-items-center bg-band px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-6 flex justify-center">
          <Wordmark size="lg" />
        </Link>
        <form
          onSubmit={onSubmit}
          className="rounded-3xl border border-line bg-white p-6 sm:p-8"
          noValidate
        >
          <h1 className="text-xl font-semibold text-ink">Admin-Anmeldung</h1>
          <p className="mt-1 text-label text-muted">
            Bitte mit deinem Betreiber-Konto anmelden.
          </p>

          {error && (
            <div
              role="alert"
              className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700"
            >
              {error}
            </div>
          )}

          <label className="mt-5 block">
            <span className="text-label font-medium text-ink">E-Mail</span>
            <input
              type="email"
              autoComplete="username"
              className={`mt-1.5 ${inputCls}`}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="mt-4 block">
            <span className="text-label font-medium text-ink">Passwort</span>
            <input
              type="password"
              autoComplete="current-password"
              className={`mt-1.5 ${inputCls}`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          <button
            type="submit"
            disabled={busy || !email || !password}
            className="mt-6 w-full rounded-lg bg-teal px-4 py-2.5 text-ui font-medium text-white transition-colors hover:bg-teal-hover disabled:opacity-50"
          >
            {busy ? "Anmelden…" : "Anmelden"}
          </button>
        </form>
      </div>
    </div>
  );
}
