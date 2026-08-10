import { useEffect, useState, type RefObject } from "react";
import { avatarColor, commentThreads, initials, type CommentThread, type FeedPost } from "../lib/communityFeed";
import { PlusIcon } from "../lib/icons";
import InlineTipComposer from "./InlineTipComposer";
import OverlayPanel from "./OverlayPanel";

/**
 * Kommentare overlay (Figma Frame_11) — the spot's comments as single-level
 * threads: each top-level comment with its replies nested underneath. "Antworte"
 * opens an inline reply mask on that comment; the round "+" FAB opens a
 * new-comment mask. Triggered only by the teaser's "mehr" link.
 */
export default function CommentsOverlay({
  open,
  onClose,
  triggerRef,
  posts,
  spotId,
  onReload,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  posts: FeedPost[];
  spotId?: string;
  /** Refetch the feed after a new comment/reply is posted. */
  onReload?: () => void;
}) {
  const [composeNew, setComposeNew] = useState(false);

  useEffect(() => {
    if (!open) setComposeNew(false);
  }, [open]);

  const threads = commentThreads(posts);

  return (
    <OverlayPanel open={open} onClose={onClose} triggerRef={triggerRef}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[28px] font-semibold leading-tight text-ink sm:text-[32px]">Kommentare</h2>
        <p className="text-ui text-muted">Kommentare und Tipps aus der Community</p>
      </div>

      {composeNew && spotId && (
        <div className="mt-6 rounded-3xl border border-line bg-surface p-5">
          <InlineTipComposer
            spotId={spotId}
            onPosted={() => {
              onReload?.();
              setComposeNew(false);
            }}
            onCancel={() => setComposeNew(false)}
          />
        </div>
      )}

      {threads.length === 0 ? (
        <p className="mt-8 text-body text-muted">Noch keine Kommentare oder Tipps — sei die/der Erste.</p>
      ) : (
        <div className="mt-6 grid items-start gap-x-6 gap-y-4 md:grid-cols-2">
          {threads.map((thread) => (
            <ThreadCard key={thread.comment.id} thread={thread} spotId={spotId} onReload={onReload} />
          ))}
        </div>
      )}

      {!composeNew && (
        <button
          type="button"
          onClick={() => setComposeNew(true)}
          aria-label="Kommentar verfassen"
          className="fixed bottom-5 right-5 z-[1102] grid h-12 w-12 place-items-center rounded-2xl border border-white/15 bg-teal text-white transition-colors hover:bg-teal-hover sm:bottom-6 sm:right-6"
        >
          <PlusIcon className="text-[26px]" />
        </button>
      )}
    </OverlayPanel>
  );
}

function ThreadCard({
  thread,
  spotId,
  onReload,
}: {
  thread: CommentThread;
  spotId?: string;
  onReload?: () => void;
}) {
  const [replying, setReplying] = useState(false);
  const { comment, replies } = thread;
  const parentTipId = comment.kind === "tip" ? comment.id.replace(/^tip:/, "") : undefined;

  return (
    <div className="flex flex-col rounded-3xl border border-line bg-surface p-5">
      <CommentHead post={comment} />
      <p className="mt-3 whitespace-pre-line text-body text-ink-soft">{comment.text}</p>

      {replies.length > 0 && (
        <div className="mt-4 space-y-3 border-l border-line pl-4">
          {replies.map((reply) => (
            <div key={reply.id}>
              <CommentHead post={reply} small />
              <p className="mt-1 whitespace-pre-line text-caption text-ink-soft">{reply.text}</p>
            </div>
          ))}
        </div>
      )}

      {replying ? (
        <div className="mt-4">
          <InlineTipComposer
            spotId={spotId}
            parentId={parentTipId}
            replyToName={comment.authorName}
            onPosted={() => {
              onReload?.();
              setReplying(false);
            }}
            onCancel={() => setReplying(false)}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setReplying(true)}
          className="mt-4 self-start text-label font-medium text-teal transition-colors hover:text-teal-hover"
        >
          Antworte
        </button>
      )}
    </div>
  );
}

function CommentHead({ post, small = false }: { post: FeedPost; small?: boolean }) {
  const size = small ? "h-7 w-7" : "h-9 w-9";
  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className={`grid ${size} shrink-0 place-items-center rounded-full text-label font-semibold text-white`}
        style={{ backgroundColor: avatarColor(post.authorName) }}
      >
        {initials(post.authorName)}
      </span>
      <span className={`font-medium text-ink ${small ? "text-label" : "text-ui"}`}>{post.authorName}</span>
    </div>
  );
}
