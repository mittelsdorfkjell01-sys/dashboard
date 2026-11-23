import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AccountError, oauthProviders, oauthStartUrl, type OAuthProvider } from "../lib/account";
import { Wordmark } from "../components/ui";
import HeroImage from "../components/HeroImage";
import ScrollBackButton from "../components/ScrollBackButton";
import { useDesktopViewport } from "../lib/useAutoHideHeader";

type Mode = "login" | "register";

/*
 * Glass sign-in (2026-11-20, on the user's explicit request): a full-bleed
 * wave photograph with one translucent, blurred tile over it — the tile
 * centred on a desktop and, on a phone, the same composition cut to its
 * middle. This page deliberately steps outside DESIGN.md (blurred glass,
 * light-on-dark controls, a tinted ground): the user decided the rules do not
 * apply to sign-in and registration only, and that DESIGN.md stays as it is.
 * Nothing here is meant to be reused elsewhere. Light and dark mode look the
 * same, because the photo and the glass are dark in both.
 *
 * The photo runs through scripts/gen_hero.py (AVIF/WebP/JPEG, never
 * upscaled); <HeroImage> picks the smallest file that covers the screen. A
 * phone gets its own portrait cut of the same photo, centred on the wave
 * (hero-src/hero-auth-mobile.jpg). Only one of the two is ever mounted.
 *
 * The tile keeps its TOP edge where it is in both tabs and grows downwards —
 * smoothly — when "Registrieren" adds its fields. It is placed from the top
 * for that reason, not centred and not anchored at the foot.
 *
 * 2026-11-21, after a reference image: an uncrowded tile. Fields share the
 * tile's own colour (no lighter fill), thin strokes, a small glyph in each
 * field, nothing bold; Google and Apple under "oder weiter mit"; registration
 * is email + password twice (the display name is derived and editable later).
 */
// 11px for the small print of this page only (2026-11-21, "alles noch
// kleiner"): it is outside the design rules by the user's decision, and the
// scale steps from 12px straight to 10px, which is too small to read.
const SMALL = "text-[0.6875rem] leading-snug";
// The field text reads 12px everywhere (2026-11-22). iOS zooms the whole page
// into a focused field set below 16px, and index.css keeps every field at
// 16px on touch screens for that reason — so the input here IS 16px and is
// drawn at 75 %: 133⅓ % of the box, scaled down from its top-left corner.
// The visible box (border, radius, focus edge) is the wrapper, which is not
// scaled; glyph and eye button sit on it. Paddings are in the input's own,
// unscaled pixels: pl-12 = 36px, pr-4 = 12px, pr-12 = 36px on screen.
const FIELD_BOX =
  "relative block h-9 w-full overflow-hidden rounded-card border border-white/[0.14] transition-colors hover:border-white/25 focus-within:outline focus-within:outline-2 focus-within:-outline-offset-1 focus-within:outline-white/70";
const FIELD =
  "absolute left-0 top-0 h-[133.334%] w-[133.334%] origin-top-left scale-75 border-0 bg-transparent pl-12 pr-4 text-body text-on-photo outline-none placeholder:text-white/40 focus-visible:!outline-none";
const LABEL = `${SMALL} text-on-photo`;
const LIGHT_LINK = "text-on-photo underline underline-offset-2 decoration-white/40 hover:decoration-white";
const SUBMIT =
  "h-9 w-full rounded-card bg-[#ECE7DF] text-caption font-medium text-[#241C17] transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/80 disabled:cursor-not-allowed disabled:opacity-50";
const SOCIAL =
  "flex h-9 w-full items-center justify-center gap-2 rounded-card border border-white/[0.14] text-caption text-on-photo transition-colors hover:border-white/25 hover:bg-white/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70";

const OAUTH_ERRORS: Record<string, string> = {
  denied: "Die Anmeldung wurde abgebrochen.",
  expired: "Die Anmeldung hat zu lange gedauert. Bitte versuche es noch einmal.",
  failed: "Die Anmeldung konnte nicht bestätigt werden. Bitte versuche es noch einmal.",
  account: "Mit diesem Konto ist keine Anmeldung möglich: Der Anbieter hat keine bestätigte E-Mail-Adresse übermittelt, oder das Konto ist nicht aktiv.",
};

/**
 * Combined sign-in / registration for the public account. Backed by the real
 * /account endpoints; on success it returns to `?redirect=` (default the account
 * home).
 *
 * Registration takes the email and the password twice. The password only
 * counts once the address is proven: the confirmation link opened in this
 * browser confirms with it and signs in; opened anywhere else, it asks for the
 * password there (app/account/service.py `confirm_email`). The minimum age is
 * part of the terms, so the one box confirms it with them.
 *
 * Google and Apple appear only when the server has them configured
 * (/account/oauth/providers); their flow runs on the server and comes back
 * here with `?oauth_error=` if it fails.
 */
export default function Auth() {
  const { login, register } = useAuth();
  const desktop = useDesktopViewport();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const redirect = params.get("redirect") || "/konto";

  const [mode, setMode] = useState<Mode>(
    params.get("mode") === "register" ? "register" : "login"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(() => OAUTH_ERRORS[params.get("oauth_error") ?? ""] ?? null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [providers, setProviders] = useState<Record<OAuthProvider, boolean>>({ google: false, apple: false });

  useEffect(() => {
    let alive = true;
    void oauthProviders().then((p) => alive && setProviders(p));
    return () => {
      alive = false;
    };
  }, []);
  const social = (["google", "apple"] as OAuthProvider[]).filter((p) => providers[p]);

  // Shown once the second entry is complete enough to compare, not while the
  // person is still typing it.
  const mismatch = repeatPassword.length > 0 && repeatPassword.length >= newPassword.length && repeatPassword !== newPassword;

  const switchMode = (m: Mode) => {
    setMode(m);
    setError(null);
    setNotice(null);
  };

  const onLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate(redirect, { replace: true });
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Etwas ist schiefgelaufen.");
    } finally {
      setBusy(false);
    }
  };

  const onRegister = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword !== repeatPassword) {
      setError("Die beiden Passwörter stimmen nicht überein.");
      return;
    }
    if (!acceptedTerms) {
      setError("Bitte akzeptiere die Nutzungsbedingungen.");
      return;
    }
    setBusy(true);
    try {
      // No display name: the server derives one from the address; it can be
      // changed any time in the settings.
      await register(email, "", newPassword, { acceptedTerms });
      setMode("login");
      setNewPassword("");
      setRepeatPassword("");
      setNotice(
        "Fast geschafft: Öffne den Bestätigungslink in deinem E-Mail-Postfach. In diesem Browser bist du danach direkt angemeldet.",
      );
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Etwas ist schiefgelaufen.");
    } finally {
      setBusy(false);
    }
  };

  const passwordToggle = (
    <button
      type="button"
      onClick={() => setShowPassword((v) => !v)}
      aria-label={showPassword ? "Passwort verbergen" : "Passwort anzeigen"}
      aria-pressed={showPassword}
      className="absolute right-0 top-0 z-10 grid h-full w-9 place-items-center rounded-card text-on-photo-muted hover:text-on-photo focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/70"
    >
      <EyeIcon crossed={showPassword} />
    </button>
  );

  const passwordField = (id: string, value: string, set: (v: string) => void, opts: { placeholder: string; autoComplete: string; invalid?: boolean; toggle?: boolean; describedBy?: string }) => (
    <div className={`${FIELD_BOX} ${opts.invalid ? "!border-[#F2A69A]" : ""}`}>
      <FieldGlyph><LockIcon /></FieldGlyph>
      <input
        id={id}
        type={showPassword ? "text" : "password"}
        value={value}
        onChange={(e) => set(e.target.value)}
        placeholder={opts.placeholder}
        autoComplete={opts.autoComplete}
        minLength={opts.autoComplete === "new-password" ? 8 : undefined}
        required
        aria-invalid={opts.invalid || undefined}
        aria-describedby={opts.describedBy}
        className={`${FIELD} ${opts.toggle ? "!pr-12" : ""}`}
      />
      {opts.toggle && passwordToggle}
    </div>
  );

  const emailField = (
    <label className="flex flex-col gap-1">
      <span className={LABEL}>E-Mail</span>
      <span className={FIELD_BOX}>
        <FieldGlyph><MailIcon /></FieldGlyph>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="du@beispiel.de"
          autoComplete="email"
          required
          className={FIELD}
        />
      </span>
    </label>
  );

  return (
    <div className="relative isolate flex min-h-svh flex-col overflow-hidden bg-ink">
      <HeroImage
        key={desktop ? "landscape" : "portrait"}
        src={desktop ? "/hero-auth-1920.jpg" : "/hero-auth-mobile-1280.jpg"}
        alt=""
        // Fixed to the screen, not the page: when "Registrieren" makes the
        // page taller, an absolutely placed photo grew and re-cropped with it,
        // so the wave visibly shifted on every tab change.
        className="fixed inset-0 -z-10 h-full w-full object-cover"
        // The wave breaks left of centre in the landscape frame.
        focal={desktop ? { x: 40, y: 50 } : { x: 50, y: 50 }}
      />
      <div aria-hidden className="fixed inset-0 -z-10 bg-[rgba(14,17,20,0.28)]" />
      <ScrollBackButton alwaysVisible onPhoto />

      {/* Placed from the top, so the top edge stays put when the tile grows. */}
      <main className="flex flex-1 flex-col items-center px-4 pt-[max(6.5rem,16svh)] sm:px-8 sm:pt-[max(5rem,calc(50svh-16rem))]">
        <div className="relative isolate flex w-full max-w-[316px] flex-col px-5 pb-5 pt-3.5 text-on-photo sm:px-6 sm:pb-5 sm:pt-4">
          {/* The glass is a layer of its own BEHIND the content. With the
              backdrop-filter on the tile itself, Chrome rendered the text into
              the filter's compositing layer, and at a fractional position (the
              tile is placed in svh) that text came out soft. */}
          <div
            aria-hidden
            className="absolute inset-0 -z-10 rounded-card border border-white/[0.10] bg-[rgba(20,24,27,0.62)] backdrop-blur-xl backdrop-saturate-[1.1]"
          />
          <Link to="/" className="mx-auto flex min-h-9 select-none items-center [&_.wordmark]:!text-on-photo">
            <Wordmark size="sm" />
          </Link>

          <h1 className="sr-only">{mode === "login" ? "Willkommen zurück" : "Konto erstellen"}</h1>

          <div className="mt-2 grid grid-cols-2 border-b border-white/[0.12]">
            {(["login", "register"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                aria-pressed={mode === m}
                // Focus is a light tint of the tab, not an outline: an outline
                // 2px off the tab lost its top and bottom in the hairline and
                // the underline, and what stayed read as two stray vertical
                // bars beside the active tab. No tap highlight either.
                className={`min-h-9 rounded-t-card text-caption transition-colors [-webkit-tap-highlight-color:transparent] focus-visible:!outline-none focus-visible:bg-white/[0.08] ${
                  mode === m
                    ? "text-on-photo shadow-[inset_0_-1.5px_0_rgba(248,246,242,1)]"
                    : "text-on-photo-muted hover:text-on-photo"
                }`}
              >
                {m === "login" ? "Anmelden" : "Registrieren"}
              </button>
            ))}
          </div>

          <SmoothHeight>
            <div className="pt-4">
              {mode === "login" ? (
                <form onSubmit={onLogin} className="flex flex-col">
                  <div className="space-y-3">
                    {emailField}
                    <div className="flex flex-col gap-1">
                      <label htmlFor="auth-password" className={LABEL}>Passwort</label>
                      {passwordField("auth-password", password, setPassword, { placeholder: "••••••••", autoComplete: "current-password", toggle: true })}
                      <Link
                        to="/passwort-zuruecksetzen"
                        className={`ml-auto inline-flex min-h-7 items-center ${SMALL} ${LIGHT_LINK}`}
                      >
                        Passwort vergessen?
                      </Link>
                    </div>
                  </div>
                  <div className="pt-2">
                    <button type="submit" disabled={busy} className={SUBMIT}>
                      {busy ? "Bitte warten …" : "Anmelden"}
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={onRegister} className="flex flex-col">
                  <div className="space-y-3">
                    {emailField}
                    <div className="flex flex-col gap-1">
                      <label htmlFor="auth-new-password" className={LABEL}>Passwort</label>
                      {passwordField("auth-new-password", newPassword, setNewPassword, { placeholder: "Mindestens 8 Zeichen", autoComplete: "new-password", toggle: true })}
                    </div>
                    <div className="flex flex-col gap-1">
                      <label htmlFor="auth-repeat-password" className={LABEL}>Passwort bestätigen</label>
                      {passwordField("auth-repeat-password", repeatPassword, setRepeatPassword, {
                        placeholder: "Passwort wiederholen",
                        autoComplete: "new-password",
                        invalid: mismatch,
                        describedBy: mismatch ? "auth-repeat-password-hint" : undefined,
                      })}
                      {mismatch && (
                        <span id="auth-repeat-password-hint" className={`${SMALL} text-[#F7C1B8]`}>
                          Die Passwörter stimmen nicht überein.
                        </span>
                      )}
                    </div>
                    <label className={`flex items-start gap-2 pt-0.5 ${SMALL} text-on-photo-muted`}>
                      <input
                        type="checkbox"
                        checked={acceptedTerms}
                        onChange={(e) => setAcceptedTerms(e.target.checked)}
                        className="mt-px h-3.5 w-3.5 shrink-0 accent-[#ECE7DF]"
                      />
                      <span>
                        Ich akzeptiere die{" "}
                        <Link to="/nutzungsbedingungen" target="_blank" rel="noopener noreferrer" className={LIGHT_LINK}>
                          Nutzungsbedingungen
                        </Link>{" "}
                        und kenne die{" "}
                        <Link to="/datenschutz" target="_blank" rel="noopener noreferrer" className={LIGHT_LINK}>
                          Datenschutzerklärung
                        </Link>
                        .
                      </span>
                    </label>
                  </div>
                  <div className="pt-3">
                    <button type="submit" disabled={busy || !acceptedTerms} className={SUBMIT}>
                      {busy ? "Bitte warten …" : "Konto erstellen"}
                    </button>
                  </div>
                </form>
              )}

              {error && (
                <p role="alert" className={`mt-3 rounded-card bg-danger-bg px-3 py-2 ${SMALL} text-danger`}>
                  {error}
                </p>
              )}
              {notice && (
                <p role="status" className={`mt-3 rounded-card bg-success-bg px-3 py-2 ${SMALL} text-success`}>
                  {notice}
                </p>
              )}

              {social.length > 0 && (
                <div className="mt-4">
                  <div className={`flex items-center gap-3 ${SMALL} text-on-photo-muted`}>
                    <span aria-hidden className="h-px flex-1 bg-white/[0.12]" />
                    oder weiter mit
                    <span aria-hidden className="h-px flex-1 bg-white/[0.12]" />
                  </div>
                  <div className="mt-3 space-y-2">
                    {social.map((p) => {
                      // On the registration tab the box above is the consent
                      // for these too: until it is ticked they wait, like
                      // "Konto erstellen".
                      const locked = mode === "register" && !acceptedTerms;
                      return (
                      // A navigation, not a fetch: the provider's page opens
                      // in the browser and comes back to the API.
                      <a
                        key={p}
                        href={locked ? undefined : oauthStartUrl(p, redirect)}
                        aria-disabled={locked || undefined}
                        role={locked ? "link" : undefined}
                        className={`${SOCIAL} ${locked ? "pointer-events-none opacity-50" : ""}`}
                      >
                        {p === "google" ? <GoogleIcon /> : <AppleIcon />}
                        Mit {p === "google" ? "Google" : "Apple"} fortfahren
                      </a>
                      );
                    })}
                  </div>
                  {/* An account created this way records the terms as accepted
                      (app/account/service.py sign_in_with_identity), so say so
                      before the click — on the sign-in tab. Registering already
                      asks for it with the box above. */}
                  {mode === "login" && <p className={`mt-2.5 text-center ${SMALL} text-on-photo-muted`}>
                    Damit akzeptierst du die{" "}
                    <Link to="/nutzungsbedingungen" target="_blank" rel="noopener noreferrer" className={LIGHT_LINK}>Nutzungsbedingungen</Link>{" "}
                    und kennst die{" "}
                    <Link to="/datenschutz" target="_blank" rel="noopener noreferrer" className={LIGHT_LINK}>Datenschutzerklärung</Link>.
                  </p>}
                </div>
              )}

              <p className={`mt-3 text-center ${SMALL} text-on-photo-muted`}>
                {mode === "login" ? "Noch kein Konto? " : "Schon ein Konto? "}
                <button
                  type="button"
                  onClick={() => switchMode(mode === "login" ? "register" : "login")}
                  className="inline-flex min-h-7 items-center font-medium text-on-photo hover:underline"
                >
                  {mode === "login" ? "Registrieren" : "Anmelden"}
                </button>
              </p>
            </div>
          </SmoothHeight>
        </div>
      </main>

      <footer className="mt-auto px-4 py-3 text-center text-caption text-on-photo-muted">
        <Link to="/impressum" className="inline-flex min-h-11 items-center px-1 text-on-photo hover:underline">Impressum</Link>
        <span aria-hidden> · </span>
        <Link to="/datenschutz" className="inline-flex min-h-11 items-center px-1 text-on-photo hover:underline">Datenschutz</Link>
        <span aria-hidden> · </span>
        <Link to="/nutzungsbedingungen" className="inline-flex min-h-11 items-center px-1 text-on-photo hover:underline">Nutzungsbedingungen</Link>
      </footer>
    </div>
  );
}

/**
 * Lets the tile grow and shrink smoothly when its content changes height.
 * CSS cannot transition `height: auto` in every browser (Safari lacks
 * `interpolate-size`), so the content is measured and its height set
 * explicitly. The first measurement applies without a transition, so the page
 * does not animate open on load; reduced motion skips the transition.
 */
function SmoothHeight({ children }: { children: ReactNode }) {
  const inner = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>();
  const [animate, setAnimate] = useState(false);

  useLayoutEffect(() => {
    const node = inner.current;
    if (!node) return;
    setHeight(node.offsetHeight);
    const observer = new ResizeObserver(() => setHeight(node.offsetHeight));
    observer.observe(node);
    // Only after the first frame: changes from then on animate.
    const frame = requestAnimationFrame(() => setAnimate(true));
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div
      data-smooth-height
      // 4px of room on every side, given back by the negative margin: the
      // clip must not cut the focus rings of full-width buttons.
      className={`-m-1 overflow-hidden p-1 ${animate ? "transition-[height] duration-slow ease-brand motion-reduce:transition-none" : ""}`}
      style={height === undefined ? undefined : { height: height + 8, boxSizing: "border-box" }}
    >
      <div ref={inner}>{children}</div>
    </div>
  );
}

function FieldGlyph({ children }: { children: ReactNode }) {
  return (
    <span aria-hidden className="pointer-events-none absolute inset-y-0 left-3 z-10 flex items-center text-on-photo-muted">
      {children}
    </span>
  );
}

const STROKE = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function MailIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" {...STROKE}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6.5 8.5-6.5" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" {...STROKE}>
      <rect x="4.5" y="10.5" width="15" height="10" rx="2" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function EyeIcon({ crossed }: { crossed: boolean }) {
  return (
    <svg aria-hidden width="15" height="15" viewBox="0 0 24 24" {...STROKE}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
      {crossed && <path d="M4 4l16 16" />}
    </svg>
  );
}

/** Google's "G" in its own colours, as its sign-in branding asks. */
function GoogleIcon() {
  return (
    <svg aria-hidden width="14" height="14" viewBox="0 0 48 48">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.6 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.2-.1-2.3-.4-3.5z" />
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg aria-hidden width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <path d="M16.37 12.54c-.02-2.2 1.8-3.26 1.88-3.31-1.03-1.5-2.62-1.7-3.18-1.73-1.35-.14-2.64.8-3.33.8-.69 0-1.74-.78-2.87-.76-1.47.02-2.83.86-3.59 2.18-1.53 2.66-.39 6.6 1.1 8.76.73 1.06 1.6 2.24 2.73 2.2 1.1-.04 1.51-.71 2.84-.71 1.32 0 1.7.71 2.86.69 1.18-.02 1.93-1.07 2.65-2.13.84-1.22 1.18-2.41 1.2-2.47-.03-.01-2.3-.88-2.32-3.52zM14.2 6.07c.6-.73 1.01-1.75.9-2.76-.87.04-1.92.58-2.54 1.31-.56.64-1.05 1.67-.92 2.66.97.08 1.96-.49 2.56-1.21z" />
    </svg>
  );
}
