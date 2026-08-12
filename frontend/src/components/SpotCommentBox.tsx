import type { RefObject } from "react";
import { avatarColor, commentThreads, initials, relativeTime, type FeedPost } from "../lib/communityFeed";
import InlineTipComposer from "./InlineTipComposer";
import UpvoteButton from "./UpvoteButton";
import type { TipItem } from "../lib/api";

export default function SpotCommentBox({ spotId, posts, onOpenMore, onPosted, overlayTriggerRef, loading = false, error = null }: { spotId?: string; posts: FeedPost[]; onOpenMore: () => void; onPosted?: (tip?: TipItem) => void; overlayTriggerRef?: RefObject<HTMLButtonElement>; loading?: boolean; error?: string | null }) {
  const threads = commentThreads(posts);
  return <section aria-labelledby="spot-comments-title" className="flex min-w-0 flex-col lg:h-full">
    <h2 id="spot-comments-title" className="sr-only">Kommentare</h2>
    <div className="min-h-0 flex-1 lg:overflow-y-auto lg:pr-2">
      {loading && threads.length === 0 ? <CommentSkeleton /> : error && threads.length === 0 ? <div role="alert" className="py-8 text-body text-muted">Kommentare konnten nicht geladen werden. <button type="button" onClick={() => onPosted?.()} className="font-medium text-teal underline">Erneut versuchen</button></div> : threads.length === 0 ? <div className="py-8"><p className="text-body font-semibold text-ink">Teile deine Erfahrung mit diesem Spot</p><p className="mt-2 text-label leading-relaxed text-muted">Hilfreich sind Bedingungen, Einstieg, Gefahren oder Tipps zu ähnlichen Spots.</p></div> : <div className="space-y-7">
        {threads.map((thread, index) => <article key={thread.comment.id} className="min-w-0">
          <CommentRow post={thread.comment} onOpen={onOpenMore} triggerRef={index === 0 ? overlayTriggerRef : undefined} />
          {thread.replies.length > 0 && <div className="ml-8 mt-4 space-y-4 border-l border-line/60 pl-3 lg:ml-11 lg:pl-4">{thread.replies.map(reply => <CommentRow key={reply.id} post={reply} onOpen={onOpenMore} compact />)}</div>}
        </article>)}
      </div>}
    </div>
    <div className="mx-auto mt-5 w-full max-w-[360px] shrink-0"><InlineTipComposer spotId={spotId} onPosted={onPosted} autoFocus={false} compact draftKey={`spot-comment:${spotId ?? "unknown"}`} /></div>
  </section>;
}

function CommentRow({ post, onOpen, triggerRef, compact = false }: { post: FeedPost; onOpen: () => void; triggerRef?: RefObject<HTMLButtonElement>; compact?: boolean }) {
  const anonymous = !post.authorName || post.authorName === "Anonym";
  const rawId = post.id.replace(/^(tip|rating):/, "");
  return <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-3">
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-full text-caption font-semibold ${compact ? "h-7 w-7" : "h-9 w-9"} ${anonymous ? "bg-band text-muted" : "text-white"}`} style={anonymous ? undefined : { backgroundColor: avatarColor(post.authorName) }}>{anonymous ? "?" : initials(post.authorName)}</span>
    <div className={`flex min-w-0 items-center ${compact ? "min-h-7" : "min-h-9"}`}>
      <strong className={`${compact ? "text-label" : "text-ui"} truncate font-semibold text-ink`}>{post.authorName || "Anonym"}</strong>
    </div>
    <div aria-hidden />
    <div className="min-w-0 pt-2">
      <button ref={triggerRef} type="button" onClick={onOpen} className="comment-entry flex min-h-11 w-full flex-col justify-center border-l border-line bg-transparent pl-3 text-left [-webkit-tap-highlight-color:transparent] focus-visible:border-teal focus-visible:outline-none">
        {post.title && <span className="mb-1 block text-label font-semibold text-ink">{post.title}</span>}
        <p className={`${compact ? "text-label" : "text-ui"} whitespace-pre-line leading-relaxed text-ink-soft`}>{post.text}</p>
      </button>
      <div className="mt-1 flex min-h-10 items-center justify-between gap-3 text-caption text-muted">
        <span className="flex items-center gap-3"><button type="button" onClick={onOpen} className="min-h-11 font-medium hover:text-ink">Antworten</button><time dateTime={post.createdAt}>{relativeTime(post.createdAt)}</time></span>
        {post.kind !== "photo" && <UpvoteButton kind={post.kind} id={rawId} count={post.upvotes} active={post.viewerUpvoted} />}
      </div>
    </div>
  </div>;
}

function CommentSkeleton() { return <div role="status" aria-live="polite" className="space-y-7 py-2"><span className="sr-only">Kommentare werden geladen</span><div aria-hidden className="h-16 animate-pulse rounded-2xl bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-2xl bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-2xl bg-band"/></div>; }
