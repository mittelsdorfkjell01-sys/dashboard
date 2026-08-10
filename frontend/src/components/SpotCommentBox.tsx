import { useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { commentThreads, type FeedPost } from "../lib/communityFeed";
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
          <button ref={moreButtonRef} type="button" onClick={onOpenMore} className="text-label font-medium text-teal transition-colors hover:text-teal-hover">
            Alle ansehen
          </button>
        )}
      </div>

      {threads.length > 0 ? (
        <>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-2">
            {threads.map(({ comment }) => (
              <button
                key={comment.id}
                type="button"
                onClick={onOpenMore}
                aria-label={`Kommentar von ${comment.authorName} vollständig öffnen`}
                className="aspect-[3/2] min-w-0 overflow-hidden rounded-2xl bg-surface p-4 text-left transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
              >
                {comment.title && <h3 className="truncate text-ui font-semibold text-ink">{comment.title}</h3>}
                <div className={`${comment.title ? "mt-1" : ""} flex items-center gap-2 text-caption text-muted`}>
                  <span className="truncate font-medium text-ink-soft">{comment.authorName || "Anonym"}</span>
                  <span aria-hidden>·</span>
                  <time dateTime={comment.createdAt}>{new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(new Date(comment.createdAt))}</time>
                </div>
                <p className="mt-3 line-clamp-3 whitespace-pre-line text-caption leading-relaxed text-ink-soft">{comment.text}</p>
              </button>
            ))}
          </div>
          <div className="mt-5 flex justify-center sm:col-span-2">
            <button type="button" onClick={startCompose} className="min-h-11 rounded-2xl bg-teal px-5 py-2.5 text-label font-medium text-white transition-colors hover:bg-teal-hover">
              Kommentar schreiben
            </button>
          </div>
        </>
      ) : (
        <div className="mt-4 rounded-2xl bg-surface px-5 py-8 text-center">
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
