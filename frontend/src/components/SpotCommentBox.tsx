import { useState } from "react";
import { avatarColor, commentThreads, initials, relativeTime, type CommentThread, type FeedPost } from "../lib/communityFeed";
import InlineTipComposer from "./InlineTipComposer";
import UpvoteButton from "./UpvoteButton";
import type { TipItem } from "../lib/api";

const INITIAL_VISIBLE = 6;
const PAGE_SIZE = 6;

/**
 * Kommentare als redaktionelle Zeilenliste — keine separate Overlay-Ansicht
 * mehr: das war eine zweite Implementierung derselben Daten (Card-Grid statt
 * Zeilen) für exakt dieselbe Liste, die hier schon vollständig sichtbar ist.
 * Antworten passiert inline pro Thread; ab `INITIAL_VISIBLE` Threads blendet
 * ein "weitere laden"-Link den Rest lokal ein (Daten sind bereits geladen).
 */
export default function SpotCommentBox({ spotId, posts, onPosted, loading = false, error = null }: { spotId?: string; posts: FeedPost[]; onPosted?: (tip?: TipItem) => void; loading?: boolean; error?: string | null }) {
  const threads = commentThreads(posts);
  const [visible, setVisible] = useState(INITIAL_VISIBLE);
  const shown = threads.slice(0, visible);

  return <section aria-labelledby="spot-comments-title" className="flex min-w-0 flex-col lg:h-full">
    <h2 id="spot-comments-title" className="text-ui font-semibold text-ink">Kommentare</h2>
    <div className="min-h-0 flex-1 lg:mt-2 lg:overflow-y-auto lg:pr-2">
      <div className="mt-7 lg:mt-2">
        {loading && threads.length === 0 ? <CommentSkeleton /> : error && threads.length === 0 ? <div role="alert" className="py-8 text-body text-muted">Kommentare konnten nicht geladen werden. <button type="button" onClick={() => onPosted?.()} className="font-medium text-teal underline">Erneut versuchen</button></div> : threads.length === 0 ? <div className="py-8"><p className="text-body font-semibold text-ink">Teile deine Erfahrung mit diesem Spot</p><p className="mt-2 text-label leading-relaxed text-muted">Hilfreich sind Bedingungen, Einstieg, Gefahren oder Tipps zu ähnlichen Spots.</p></div> : <div className="space-y-7">
          {shown.map(thread => <ThreadRow key={thread.comment.id} thread={thread} spotId={spotId} onPosted={onPosted} />)}
        </div>}
      </div>
      {visible < threads.length && <button type="button" onClick={() => setVisible(v => v + PAGE_SIZE)} className="mt-6 min-h-11 self-start text-label font-medium text-teal transition-colors hover:text-teal-hover">Weitere Kommentare laden ({threads.length - visible})</button>}
    </div>
    <div className="mx-auto mt-6 w-full max-w-[420px] shrink-0"><InlineTipComposer spotId={spotId} onPosted={onPosted} autoFocus={false} compact draftKey={`spot-comment:${spotId ?? "unknown"}`} /></div>
  </section>;
}

function ThreadRow({ thread, spotId, onPosted }: { thread: CommentThread; spotId?: string; onPosted?: (tip?: TipItem) => void }) {
  const [replying, setReplying] = useState(false);
  const { comment, replies } = thread;
  const parentTipId = comment.kind === "tip" ? comment.id.replace(/^tip:/, "") : undefined;

  return <article className="min-w-0">
    <CommentRow post={comment} />
    {replies.length > 0 && <div className="ml-8 mt-4 space-y-4 border-l border-line/60 pl-3 lg:ml-11 lg:pl-4">{replies.map(reply => <CommentRow key={reply.id} post={reply} compact />)}</div>}
    <div className="ml-8 mt-2 lg:ml-11">
      {replying ? <div className="mt-2 max-w-[420px]"><InlineTipComposer spotId={spotId} parentId={parentTipId} replyToName={comment.authorName} onPosted={(tip) => { onPosted?.(tip); setReplying(false); }} onCancel={() => setReplying(false)} /></div> : <button type="button" onClick={() => setReplying(true)} className="min-h-11 text-caption font-medium text-muted transition-colors hover:text-ink">Antworten</button>}
    </div>
  </article>;
}

function CommentRow({ post, compact = false }: { post: FeedPost; compact?: boolean }) {
  const anonymous = !post.authorName || post.authorName === "Anonym";
  const rawId = post.id.replace(/^(tip|rating):/, "");
  return <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-3">
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-full text-caption font-semibold ${compact ? "h-7 w-7" : "h-9 w-9"} ${anonymous ? "bg-band text-muted" : "text-white"}`} style={anonymous ? undefined : { backgroundColor: avatarColor(post.authorName) }}>{anonymous ? "?" : initials(post.authorName)}</span>
    <div className={`flex min-w-0 items-center ${compact ? "min-h-7" : "min-h-9"}`}>
      <strong className={`${compact ? "text-label" : "text-ui"} truncate font-semibold text-ink`}>{post.authorName || "Anonym"}</strong>
    </div>
    <div aria-hidden />
    <div className="min-w-0 pt-2">
      {post.title && <span className="mb-1 block text-label font-semibold text-ink">{post.title}</span>}
      <p className={`${compact ? "text-label" : "text-ui"} whitespace-pre-line leading-relaxed text-ink-soft`}>{post.text}</p>
      <div className="mt-1 flex min-h-10 items-center gap-3 text-caption text-muted">
        <time dateTime={post.createdAt}>{relativeTime(post.createdAt)}</time>
        {post.kind !== "photo" && <UpvoteButton kind={post.kind} id={rawId} count={post.upvotes} active={post.viewerUpvoted} />}
      </div>
    </div>
  </div>;
}

function CommentSkeleton() { return <div role="status" aria-live="polite" className="space-y-7 py-2"><span className="sr-only">Kommentare werden geladen</span><div aria-hidden className="h-16 animate-pulse rounded-[14px] bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-[14px] bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-[14px] bg-band"/></div>; }
