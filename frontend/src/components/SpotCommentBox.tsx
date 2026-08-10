import { useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { avatarColor, initials, type FeedPost } from "../lib/communityFeed";
import { useAuth } from "../context/AuthContext";
import CommentAuthChoiceDialog from "./CommentAuthChoiceDialog";
import CommentModal from "./CommentModal";

/** Small speech-bubble icon for the "Kommentar verfassen" entry. */
function CommentIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9.9 9.9 0 0 1-4.3-1L3 20l1.1-4.2A8.4 8.4 0 1 1 21 11.5Z" />
    </svg>
  );
}

/**
 * Info-tab comment tile (under the facilities). Shows the newest comment when
 * one exists, otherwise a "write the first one" prompt. Composing runs through a
 * flow: "Kommentar verfassen" → auth choice (anonym / anmelden) → a central
 * comment modal (dimmed + blurred backdrop). "mehr" opens the full overlay.
 */
export default function SpotCommentBox({
  spotId,
  comment,
  onOpenMore,
  onPosted,
  moreButtonRef,
  variant = "card",
}: {
  spotId?: string;
  comment: FeedPost | null;
  onOpenMore: () => void;
  onPosted?: () => void;
  moreButtonRef?: RefObject<HTMLButtonElement>;
  variant?: "card" | "plain";
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  // The pending compose target (null = closed); step drives choice vs. modal.
  const [pending, setPending] = useState<{ parentId?: string; replyToName?: string } | null>(null);
  const [step, setStep] = useState<"choose" | "compose" | null>(null);
  const [author, setAuthor] = useState("Anonym");

  // Only a tip can be replied to (the backend parent is a local_tip).
  const replyTargetId =
    comment && comment.kind === "tip" ? comment.id.replace(/^tip:/, "") : undefined;

  // Signed in → straight to the modal; signed out → offer the auth choice first.
  const startCompose = (target: { parentId?: string; replyToName?: string }) => {
    setPending(target);
    if (user) {
      setAuthor(user.displayName);
      setStep("compose");
    } else {
      setStep("choose");
    }
  };

  const reset = () => {
    setStep(null);
    setPending(null);
  };

  const posted = () => {
    onPosted?.();
    reset();
  };

  return (
    <div
      className={
        variant === "plain"
          ? "flex h-full min-h-0 flex-col py-1"
          : "flex flex-1 flex-col rounded-3xl bg-white p-6 shadow-card"
      }
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-label text-muted">Kommentare oder Tips</p>
        {comment && (
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

      {comment ? (
        <>
          <div className="mt-4 min-h-0 flex-1 overflow-hidden">
            <div className="flex items-center gap-2.5">
              <span
                aria-hidden="true"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-label font-semibold text-white"
                style={{ backgroundColor: avatarColor(comment.authorName) }}
              >
                {initials(comment.authorName)}
              </span>
              <span className="text-ui font-medium text-ink">{comment.authorName}</span>
            </div>
            <p className="mt-3 whitespace-pre-line text-body text-ink-soft">{comment.text}</p>
          </div>
          <div className={`mt-auto flex items-center text-label font-medium text-teal ${variant === "plain" ? "justify-between gap-3 border-t border-line pt-4" : "gap-5 pt-4"}`}>
            <button
              type="button"
              onClick={() =>
                startCompose(
                  replyTargetId
                    ? { parentId: replyTargetId, replyToName: comment.authorName }
                    : {}
                )
              }
              className="inline-flex items-center gap-1.5 transition-colors hover:text-teal-hover"
            >
              <CommentIcon />
              <span className={variant === "plain" ? "sr-only" : ""}>Antworte</span>
            </button>
            <button
              type="button"
              onClick={() => startCompose({})}
              className="inline-flex items-center gap-1.5 transition-colors hover:text-teal-hover"
            >
              <CommentIcon />
              <span className={variant === "plain" ? "sr-only" : ""}>Verfasse Kommentar / Tipp</span>
            </button>
          </div>
        </>
      ) : (
        <div className={`mt-4 flex min-h-0 flex-1 flex-col ${variant === "plain" ? "items-start justify-between text-left" : "items-center justify-center text-center"}`}>
          <p className="max-w-[26ch] text-body text-ink-soft">
            Schreibe einen Kommentar und einen Tipp für den Spot
          </p>
          <button
            type="button"
            onClick={() => startCompose({})}
            className={variant === "plain" ? "mt-auto grid h-10 w-10 place-items-center self-end rounded-full bg-teal text-white transition-colors hover:bg-teal-hover" : "mt-4 inline-flex items-center gap-2 rounded-2xl bg-teal px-5 py-2.5 text-label font-medium text-white transition-colors hover:bg-teal-hover"}
          >
            <CommentIcon />
            <span className={variant === "plain" ? "sr-only" : ""}>Kommentar verfassen</span>
          </button>
        </div>
      )}

      <CommentAuthChoiceDialog
        open={step === "choose"}
        onAnonymous={() => {
          setAuthor("Anonym");
          setStep("compose");
        }}
        onSignIn={() => navigate("/anmelden?mode=login")}
        onCancel={reset}
      />
      <CommentModal
        open={step === "compose"}
        spotId={spotId}
        parentId={pending?.parentId}
        replyToName={pending?.replyToName}
        authorName={author}
        onPosted={posted}
        onClose={reset}
      />
    </div>
  );
}
