import { useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { avatarColor, commentThreads, initials, type FeedPost } from "../lib/communityFeed";
import { useAuth } from "../context/AuthContext";
import CommentAuthChoiceDialog from "./CommentAuthChoiceDialog";
import CommentModal from "./CommentModal";

export default function SpotCommentBox({
  spotId,
  posts,
  onOpenMore,
  onPosted,
  moreButtonRef,
}: {
  spotId?: string;
  posts: FeedPost[];
  onOpenMore: () => void;
  onPosted?: () => void;
  moreButtonRef?: RefObject<HTMLButtonElement>;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<"choose" | "compose" | null>(null);
  const [author, setAuthor] = useState("Anonym");
  const threads = commentThreads(posts);

  const startCompose = () => {
    if (user) {
      setAuthor(user.displayName);
      setStep("compose");
    } else {
      setStep("choose");
    }
  };

  const close = () => setStep(null);
  const posted = () => {
    onPosted?.();
    close();
  };

  return (
    <section aria-labelledby="spot-comments-title" className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <h2 id="spot-comments-title" className="text-label font-semibold uppercase tracking-[0.08em] text-muted">Kommentare</h2>
        {threads.length > 0 && (
          <button ref={moreButtonRef} type="button" onClick={startCompose} className="text-label font-medium text-teal transition-colors hover:text-teal-hover">
            Kommentar schreiben
          </button>
        )}
      </div>

      {threads.length > 0 ? (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-2">
          {threads.map(({ comment }) => (
            <button
              key={comment.id}
              type="button"
              onClick={onOpenMore}
              aria-label={`Kommentar von ${comment.authorName} vollständig öffnen`}
              className="flex aspect-[3/2] min-w-0 flex-col overflow-hidden rounded-2xl bg-page p-4 text-left text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span
                  aria-hidden
                  className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-caption font-semibold text-white"
                  style={{ backgroundColor: avatarColor(comment.authorName || "Anonym") }}
                >
                  {initials(comment.authorName || "Anonym")}
                </span>
                <span className="truncate text-ui font-medium text-ink">{comment.authorName || "Anonym"}</span>
              </div>
              {comment.title && <h3 className="mt-3 truncate text-ui font-semibold text-ink">{comment.title}</h3>}
              <p className="mt-2 line-clamp-3 whitespace-pre-line text-caption leading-relaxed text-ink">{comment.text}</p>
              <time className="mt-auto pt-2 text-caption text-muted" dateTime={comment.createdAt}>
                {new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(new Date(comment.createdAt))}
              </time>
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl bg-page px-5 py-8 text-center">
          <p className="mx-auto max-w-[34ch] text-body text-ink-soft">Teile deine Erfahrung mit diesem Spot und hilf anderen auf dem Wasser.</p>
          <button type="button" onClick={startCompose} className="mt-5 min-h-11 rounded-2xl bg-teal px-5 py-2.5 text-label font-medium text-white transition-colors hover:bg-teal-hover">
            Ersten Kommentar schreiben
          </button>
        </div>
      )}

      <CommentAuthChoiceDialog open={step === "choose"} onAnonymous={() => { setAuthor("Anonym"); setStep("compose"); }} onSignIn={() => navigate("/anmelden?mode=login")} onCancel={close} />
      <CommentModal open={step === "compose"} spotId={spotId} authorName={author} onPosted={posted} onClose={close} />
    </section>
  );
}
