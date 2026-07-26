import { useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, postTip } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import CommentAuthChoiceDialog from "./CommentAuthChoiceDialog";

/**
 * Info-tab comment box (Figma Frame_9, right column under the facilities) — a
 * always-visible inline composer: "Kommentare oder Tips", a text area, and an
 * "absenden" button. Posts through the text-only tips endpoint.
 *
 * Submitting while signed out opens the auth-choice dialog
 * (`CommentAuthChoiceDialog`): post anonymously (as "Anonym") or sign in to
 * comment under your name. Signed in, it posts straight away under the
 * account's display name. A "mehr" link (only when comments exist) opens the
 * full Kommentare overlay.
 */
export default function SpotCommentBox({
  spotId,
  hasComments,
  onOpenMore,
  onPosted,
  moreButtonRef,
}: {
  spotId?: string;
  hasComments: boolean;
  onOpenMore: () => void;
  onPosted?: () => void;
  /** So the overlay can return focus to the "mehr" link on close. */
  moreButtonRef?: RefObject<HTMLButtonElement>;
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
      await postTip(spotId, { body: text.trim(), author_name: authorName });
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
    <div className="rounded-3xl bg-white p-6 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <p className="text-label text-muted">Kommentare oder Tips</p>
        {hasComments && (
          <button
            ref={moreButtonRef}
            type="button"
            onClick={onOpenMore}
            className="text-label font-medium text-teal transition-colors hover:text-teal-hover"
          >
            mehr
          </button>
        )}
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="verfasse einen Kommentar…"
        rows={5}
        className="mt-3 w-full resize-none rounded-2xl border border-line bg-white p-4 text-body text-ink placeholder:text-muted focus:border-teal/40 focus:outline-none focus:ring-2 focus:ring-teal/20"
      />

      {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={onSend}
          disabled={busy || !text.trim()}
          className="rounded-full bg-teal px-5 py-2 text-label font-medium text-white transition-colors hover:bg-teal-hover disabled:opacity-40"
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
        onSignIn={() => navigate("/anmelden")}
        onCancel={() => setAuthOpen(false)}
      />
    </div>
  );
}
