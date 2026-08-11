import { useEffect, useState, type RefObject } from "react";
import { avatarColor, commentThreads, initials, type CommentThread, type FeedPost } from "../lib/communityFeed";
import { PlusIcon } from "../lib/icons";
import InlineTipComposer from "./InlineTipComposer";
import OverlayPanel from "./OverlayPanel";
import UpvoteButton from "./UpvoteButton";

/**
 * Kommentare overlay (Figma Frame_11) — the spot's comments as single-level
 * threads: each top-level comment with its replies nested underneath. "Antworte"
 * opens an inline reply mask on that comment; the round "+" FAB opens a
 * new-comment mask. Triggered by clicking a comment tile in `SpotCommentBox`.
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
        <div className="mt-6 rounded-3xl bg-band p-5">
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
    <div className="flex flex-col rounded-3xl bg-band p-5">
      <CommentHead post={comment} />
      {comment.title && <h3 className="mt-3 text-body font-semibold text-ink">{comment.title}</h3>}
      <p className="mt-3 whitespace-pre-line text-body text-ink-soft">{comment.text}</p>
      {comment.kind !== "photo" && <div className="mt-1"><UpvoteButton kind={comment.kind} id={comment.id.replace(/^(tip|rating):/, "")} count={comment.upvotes} active={comment.viewerUpvoted} /></div>}

      {replies.length > 0 && (
        <div className="mt-4 space-y-3 pl-4">
          {replies.map((reply) => (
            <div key={reply.id}>
              <CommentHead post={reply} small />
              <p className="mt-1 whitespace-pre-line text-caption text-ink-soft">{reply.text}</p>
              {reply.kind !== "photo" && <UpvoteButton kind={reply.kind} id={reply.id.replace(/^(tip|rating):/, "")} count={reply.upvotes} active={reply.viewerUpvoted} />}
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
          aria-label="Kommentar schreiben"
          title="Kommentieren"
          className="mt-4 grid h-10 w-10 place-items-center self-start rounded-full text-teal transition-colors hover:bg-surface hover:text-teal-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
        >
          <CommentBubbleIcon />
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
      <span className="min-w-0">
        <span className={`block font-medium text-ink ${small ? "text-label" : "text-ui"}`}>{post.authorName}</span>
        <time className="block text-caption text-muted" dateTime={post.createdAt}>{new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(new Date(post.createdAt))}</time>
      </span>
    </div>
  );
}

function CommentBubbleIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9.9 9.9 0 0 1-4.3-1L3 20l1.1-4.2A8.4 8.4 0 1 1 21 11.5Z" />
    </svg>
  );
}
