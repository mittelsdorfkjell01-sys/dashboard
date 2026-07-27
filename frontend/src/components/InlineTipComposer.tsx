import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, postTip } from "../lib/api";
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
}: {
  spotId?: string;
  /** Raw parent tip id — set to post this as a reply. */
  parentId?: string;
  /** Shown as "Antwort an …" above the field. */
  replyToName?: string;
  onPosted?: () => void;
  /** When provided, a "✕ abbrechen" control is shown. */
  onCancel?: () => void;
  autoFocus?: boolean;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);

  const post = async (authorName: string) => {
    if (!spotId || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await postTip(spotId, { body: text.trim(), author_name: authorName, parent_id: parentId });
      setText("");
      onPosted?.();
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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {replyToName && <p className="mb-2 text-caption text-muted">Antwort an {replyToName}</p>}
      <textarea
        autoFocus={autoFocus}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="verfasse einen Kommentar…"
        className="min-h-[110px] w-full flex-1 resize-none rounded-2xl border-[0.5px] border-line bg-white p-4 text-body text-ink placeholder:text-muted focus:border-teal/40 focus:outline-none focus:ring-2 focus:ring-teal/20"
      />
      {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}
      <div className="mt-3 flex items-center justify-between">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 text-label font-medium text-muted transition-colors hover:text-ink"
          >
            <CloseIcon width={15} height={15} />
            abbrechen
          </button>
        ) : (
          <span />
        )}
        <button
          type="button"
          onClick={onSend}
          disabled={busy || !text.trim()}
          className="rounded-full bg-teal/80 px-5 py-2 text-label font-medium text-white transition-colors hover:bg-teal disabled:opacity-40"
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
        onSignIn={() => navigate("/anmelden?mode=login")}
        onCancel={() => setAuthOpen(false)}
      />
    </div>
  );
}
