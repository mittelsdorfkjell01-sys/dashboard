import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, postTip, type TipItem } from "../lib/api";
import { CloseIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import CommentAuthChoiceDialog from "./CommentAuthChoiceDialog";

/**
 * Shared inline compose mask (used by the Info-tab comment tile and the
 * Kommentare overlay, for both new comments and replies). Text area + an
 * "absenden" button; an optional "✕ abbrechen" when `onCancel` is given.
 * Posts through the text-only tips endpoint, carrying `parentId` for replies.
 *
 * Submitting while signed out opens the auth-choice dialog (post as "Anonym"
 * or sign in). Signed in, it posts under the account display name.
 */
export default function InlineTipComposer({
  spotId,
  parentId,
  replyToName,
  onPosted,
  onCancel,
  autoFocus = true,
  compact = false,
  draftKey,
}: {
  spotId?: string;
  /** Raw parent tip id — set to post this as a reply. */
  parentId?: string;
  /** Shown as "Antwort an …" above the field. */
  replyToName?: string;
  onPosted?: (tip: TipItem) => void;
  /** When provided, a "✕ abbrechen" control is shown. */
  onCancel?: () => void;
  autoFocus?: boolean;
  compact?: boolean;
  draftKey?: string;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [text, setText] = useState(() => draftKey ? sessionStorage.getItem(draftKey) ?? "" : "");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    if (!draftKey) return;
    if (text) sessionStorage.setItem(draftKey, text);
    else sessionStorage.removeItem(draftKey);
  }, [draftKey, text]);

  const post = async (authorName: string) => {
    if (!spotId || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await postTip(spotId, { body: text.trim(), title: title.trim() || undefined, author_name: authorName, parent_id: parentId });
      setText("");
      setTitle("");
      onPosted?.(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Senden fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const onSend = () => {
    if (!text.trim()) return;
    if (!user) {
      setAuthOpen(true);
      return;
    }
    void post(user.displayName);
  };

  if (compact) {
    return (
      <div className="w-full">
        <div className="relative">
          <input
            autoFocus={autoFocus}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && text.trim() && !busy) {
                event.preventDefault();
                onSend();
              }
            }}
            maxLength={4000}
            placeholder="Kommentar hinzufügen …"
            aria-label="Kommentar hinzufügen"
            className="h-11 w-full rounded-xl border border-line bg-page py-2 pl-4 pr-12 text-[16px] text-ink placeholder:text-muted focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/10 sm:text-label"
          />
          {text.trim() && (
            <button
              type="button"
              onClick={onSend}
              disabled={busy}
              aria-label={busy ? "Kommentar wird gesendet" : "Kommentar absenden"}
              className="absolute right-0 top-0 grid h-11 w-11 place-items-center rounded-lg text-teal transition-colors hover:bg-band hover:text-teal-hover disabled:opacity-40"
            >
              {busy ? (
                <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-teal/25 border-t-teal" />
              ) : (
                <svg aria-hidden width="18" height="18" viewBox="0 0 20 20" fill="none">
                  <path d="M3 10 16.5 3.5 12 16.5l-2.2-5.1L3 10Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                  <path d="m9.8 11.4 3.2-3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              )}
            </button>
          )}
        </div>
        {error && <p role="alert" className="mt-2 text-caption text-red-600">{error}</p>}
        <CommentAuthChoiceDialog
          open={authOpen}
          onAnonymous={() => {
            setAuthOpen(false);
            void post("Anonym");
          }}
          onSignIn={() => navigate(`/anmelden?mode=login&redirect=${encodeURIComponent(location.pathname + location.search)}`)}
          onCancel={() => setAuthOpen(false)}
          title="Wie möchtest du kommentieren?"
          anonymousText="Dein Entwurf bleibt erhalten. Der Kommentar erscheint als Anonym."
          signInText="Dein Entwurf bleibt erhalten und erscheint unter deinem Namen."
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {replyToName && <p className="mb-2 text-caption text-muted">Antwort an {replyToName}</p>}
      {!parentId && !compact && (
        <div className="mb-3">
          <label htmlFor="inline-comment-title" className="text-label font-medium text-ink">Überschrift <span className="text-muted">(optional)</span></label>
          <input id="inline-comment-title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder="Worum geht es?" className="mt-2 min-h-11 w-full rounded-2xl border border-line bg-page px-4 text-body text-ink placeholder:text-muted focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/10" />
          <p className="mt-1 text-right text-caption text-muted">{title.length}/120</p>
        </div>
      )}
      <textarea
        autoFocus={autoFocus}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="verfasse einen Kommentar…"
        maxLength={4000}
        className="comment-field min-h-[110px] w-full flex-1 resize-none rounded-2xl border border-line bg-page p-4 text-body text-ink placeholder:text-muted focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/10"
      />
      {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}
      <div className="mt-2 flex items-center justify-between gap-3">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 text-label font-medium text-muted transition-colors hover:text-ink"
          >
            <CloseIcon width={15} height={15} />
            Schließen
          </button>
        ) : (
          <span className="text-caption text-muted">{text.length}/4000</span>
        )}
        <button
          type="button"
          onClick={onSend}
          disabled={busy || !text.trim()}
          className="min-h-11 px-5 py-2 text-label font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70 disabled:opacity-40 disabled:no-underline"
        >
          {busy ? "Senden…" : "absenden"}
        </button>
      </div>

      <CommentAuthChoiceDialog
        open={authOpen}
        onAnonymous={() => {
          setAuthOpen(false);
          void post("Anonym");
        }}
        onSignIn={() => navigate(`/anmelden?mode=login&redirect=${encodeURIComponent(location.pathname + location.search)}`)}
        onCancel={() => setAuthOpen(false)}
        title="Wie möchtest du kommentieren?"
        anonymousText="Dein Entwurf bleibt erhalten. Der Kommentar erscheint als Anonym."
        signInText="Dein Entwurf bleibt erhalten und erscheint unter deinem Namen."
      />
    </div>
  );
}
