import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AccountError } from "../lib/account";
import { Button, Field, Input, Wordmark } from "../components/ui";

type Mode = "login" | "register";

/**
 * Combined sign-in / registration for the public account. Backed by the real
 * /account endpoints; on success it returns to `?redirect=` (default the account
 * home).
 */
export default function Auth() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const redirect = params.get("redirect") || "/konto";

  const [mode, setMode] = useState<Mode>(
    params.get("mode") === "register" ? "register" : "login"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const switchMode = (m: Mode) => {
    setMode(m);
    setError(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      navigate(redirect, { replace: true });
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Etwas ist schiefgelaufen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-band px-4 py-12">
      <Link to="/" aria-label="surfwind data — Startseite" className="mb-8 select-none">
        <Wordmark size="lg" />
      </Link>

      <div className="w-full max-w-[420px] rounded-3xl border border-line bg-white p-6 sm:p-8">
        <div className="mb-6 grid grid-cols-2 gap-1 rounded-2xl bg-band p-1">
          {(["login", "register"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              aria-pressed={mode === m}
              className={`rounded-2xl py-2 text-[14px] font-semibold transition-colors ${
                mode === m
                  ? "bg-white text-teal"
                  : "text-muted hover:text-teal"
              }`}
            >
              {m === "login" ? "Anmelden" : "Registrieren"}
            </button>
          ))}
        </div>

        <h1 className="mb-1 text-[22px] font-semibold text-ink">
          {mode === "login" ? "Willkommen zurück" : "Konto erstellen"}
        </h1>
        <p className="mb-6 text-[14px] text-muted">
          {mode === "login"
            ? "Melde dich an, um Favoriten und eigene Spots zu verwalten."
            : "Speichere Lieblings-Spots und reiche eigene ein."}
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          {mode === "register" && (
            <Field label="Anzeigename">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="z. B. Windfinder"
                autoComplete="nickname"
              />
            </Field>
          )}
          <Field label="E-Mail" required>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="du@beispiel.de"
              autoComplete="email"
              required
            />
          </Field>
          <Field label="Passwort" required hint={mode === "register" ? "Mindestens 6 Zeichen." : undefined}>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />
          </Field>

          {error && (
            <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-[13px] font-medium text-red-700">
              {error}
            </p>
          )}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Bitte warten …" : mode === "login" ? "Anmelden" : "Konto erstellen"}
          </Button>
        </form>

        <p className="mt-5 text-center text-[13px] text-muted">
          {mode === "login" ? "Noch kein Konto? " : "Schon registriert? "}
          <button
            type="button"
            onClick={() => switchMode(mode === "login" ? "register" : "login")}
            className="font-semibold text-teal hover:underline"
          >
            {mode === "login" ? "Jetzt registrieren" : "Zur Anmeldung"}
          </button>
        </p>
      </div>
    </div>
  );
}
