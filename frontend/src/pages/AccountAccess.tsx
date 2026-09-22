import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { AccountError, confirmEmail, confirmPasswordReset, requestPasswordReset } from "../lib/account";
import { useAuth } from "../context/AuthContext";
import { Button, Field, Input, Wordmark } from "../components/ui";

export default function AccountAccess() {
  const location = useLocation();
  const { setUser } = useAuth();
  const [params] = useSearchParams();
  const [token] = useState(params.get("token") ?? "");
  const purpose = params.get("purpose") ?? "verify";
  const resetting = location.pathname === "/passwort-zuruecksetzen";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (token) window.history.replaceState(window.history.state, "", location.pathname);
  }, [token, location.pathname]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (resetting && !token) {
        await requestPasswordReset(email);
        setMessage("Falls ein bestätigtes Konto existiert, erhältst du einen Link per E-Mail.");
      } else if (resetting) {
        await confirmPasswordReset(token, password);
        setUser(null);
        setMessage("Passwort geändert. Melde dich jetzt an.");
      } else {
        await confirmEmail(token, purpose === "verify" ? password : undefined);
        if (purpose === "change_email") setUser(null);
        setMessage("E-Mail-Adresse bestätigt. Du kannst dich jetzt anmelden.");
      }
      setPassword("");
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Aktion fehlgeschlagen. Bitte versuche es erneut.");
    } finally {
      setBusy(false);
    }
  };

  const title = resetting ? "Passwort zurücksetzen" : "E-Mail bestätigen";
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-band px-4 py-12">
      <Link to="/" aria-label="Zur Startseite" className="mb-8"><Wordmark size="lg" /></Link>
      <div className="w-full max-w-[420px] rounded-[14px] border border-line bg-surface p-6 sm:p-8">
        <h1 className="text-sz-28 font-semibold text-ink">{title}</h1>
        <p className="mt-2 text-ui text-muted">
          {resetting && !token ? "Wir senden dir einen Link zum Zurücksetzen." :
           resetting ? "Wähle ein neues Passwort für dein Konto." :
           purpose === "verify" ? "Lege dein endgültiges Passwort fest und bestätige damit deine Adresse." :
           "Bestätige die neue Adresse für dein Konto."}
        </p>
        {!message && (token || resetting) && (
          <form onSubmit={submit} className="mt-6 space-y-4">
            {resetting && !token && <Field label="E-Mail"><Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>}
            {(resetting && token || !resetting && purpose === "verify") &&
              <Field label="Neues Passwort" hint="Mindestens 8 Zeichen."><Input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} /></Field>}
            {error && <p role="alert" className="text-ui text-danger">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">{busy ? "Bitte warten …" : resetting && !token ? "Link anfordern" : "Bestätigen"}</Button>
          </form>
        )}
        {!token && !resetting && <p role="alert" className="mt-5 text-ui text-danger">Der Bestätigungslink fehlt.</p>}
        {message && <p role="status" className="mt-6 rounded-lg bg-success-bg p-3 text-ui text-success">{message}</p>}
        <Link to="/anmelden" className="mt-5 inline-flex min-h-11 items-center text-ui font-semibold text-ink underline">Zur Anmeldung</Link>
      </div>
    </main>
  );
}
