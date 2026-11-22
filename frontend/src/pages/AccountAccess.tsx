import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { AccountError, confirmEmail, confirmPasswordReset, requestPasswordReset } from "../lib/account";
import { useAuth } from "../context/AuthContext";
import { Button, Field, Input, Wordmark } from "../components/ui";
import ScrollBackButton from "../components/ScrollBackButton";

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
  // A registration link first tries to confirm without a password: back in
  // the browser that registered, the password chosen there stands and the
  // person is signed in. Anywhere else the server answers 428 and this page
  // asks for the password (see app/account/service.py `confirm_email`).
  const verifying = !resetting && purpose === "verify" && Boolean(token);
  const [needsPassword, setNeedsPassword] = useState(!verifying);
  const [checking, setChecking] = useState(verifying);
  const attempted = useRef(false);

  useEffect(() => {
    if (token) window.history.replaceState(window.history.state, "", location.pathname);
  }, [token, location.pathname]);

  useEffect(() => {
    // Once: a link token is single-use, so a second (StrictMode) call would
    // fail after the first one succeeded.
    if (!verifying || attempted.current) return;
    attempted.current = true;
    confirmEmail(token)
      .then((account) => {
        setUser(account);
        setMessage("E-Mail-Adresse bestätigt. Du bist jetzt angemeldet.");
      })
      .catch((err) => {
        if (err instanceof AccountError && err.status === 428) setNeedsPassword(true);
        else setError(err instanceof AccountError ? err.message : "Aktion fehlgeschlagen. Bitte versuche es erneut.");
      })
      .finally(() => setChecking(false));
  }, [verifying, token, setUser]);

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
      <ScrollBackButton alwaysVisible />
      <Link to="/" aria-label="Zur Startseite" className="mb-8 flex min-h-11 items-center"><Wordmark size="lg" /></Link>
      <div className="w-full max-w-[420px] rounded-card border border-line bg-surface p-6 sm:p-8">
        <h1 className="text-heading font-semibold text-ink">{title}</h1>
        <p className="mt-2 text-ui text-muted">
          {resetting && !token ? "Wir senden dir einen Link zum Zurücksetzen." :
           resetting ? "Wähle ein neues Passwort für dein Konto." :
           purpose === "verify" && checking ? "Einen Moment, wir bestätigen deine Adresse …" :
           purpose === "verify" && !needsPassword ? "Deine Adresse konnte mit diesem Link nicht bestätigt werden." :
           purpose === "verify" ? "Du öffnest den Link nicht in dem Browser, in dem du dich registriert hast. Lege hier dein Passwort fest, um dein Konto zu bestätigen." :
           "Bestätige die neue Adresse für dein Konto."}
        </p>
        {!message && !checking && needsPassword && (token || resetting) && (
          <form onSubmit={submit} className="mt-6 space-y-4">
            {resetting && !token && <Field label="E-Mail"><Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>}
            {(resetting && token || !resetting && purpose === "verify") &&
              <Field label="Neues Passwort" hint="Mindestens 8 Zeichen."><Input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} /></Field>}
            {error && <p role="alert" className="text-ui text-danger">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">{busy ? "Bitte warten …" : resetting && !token ? "Link anfordern" : "Bestätigen"}</Button>
          </form>
        )}
        {error && !needsPassword && <p role="alert" className="mt-5 text-ui text-danger">{error}</p>}
        {!token && !resetting && <p role="alert" className="mt-5 text-ui text-danger">Der Bestätigungslink fehlt.</p>}
        {message && <p role="status" className="mt-6 rounded-card bg-success-bg p-3 text-ui text-success">{message}</p>}
        <Link to="/anmelden" className="mt-5 inline-flex min-h-11 items-center text-ui font-semibold text-ink underline">Zur Anmeldung</Link>
      </div>
    </main>
  );
}
