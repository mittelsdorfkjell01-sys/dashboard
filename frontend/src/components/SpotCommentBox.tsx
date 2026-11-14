import { useState } from "react";
import { avatarColor, commentThreads, initials, relativeTime, type CommentThread, type FeedPost } from "../lib/communityFeed";
import InlineTipComposer from "./InlineTipComposer";
import UpvoteButton from "./UpvoteButton";
import { ApiError, deleteOwnTip, editOwnTip, reportTip, type TipItem } from "../lib/api";

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
        {loading && threads.length === 0 ? <CommentSkeleton /> : error && threads.length === 0 ? <div role="alert" className="py-8 text-body text-muted">Kommentare konnten nicht geladen werden. <button type="button" onClick={() => onPosted?.()} className="font-medium text-accent underline">Erneut versuchen</button></div> : threads.length === 0 ? <div className="py-8"><p className="text-body font-semibold text-ink">Teile deine Erfahrung mit diesem Spot</p><p className="mt-2 text-ui leading-relaxed text-muted">Hilfreich sind Bedingungen, Einstieg, Gefahren oder Tipps zu ähnlichen Spots.</p></div> : <div className="space-y-7">
          {shown.map(thread => <ThreadRow key={thread.comment.id} thread={thread} spotId={spotId} onPosted={onPosted} />)}
        </div>}
      </div>
      {visible < threads.length && <button type="button" onClick={() => setVisible(v => v + PAGE_SIZE)} className="mt-6 min-h-11 self-start text-ui font-medium text-accent transition-colors hover:text-accent-hover">Weitere Kommentare laden ({threads.length - visible})</button>}
    </div>
    <div className="mx-auto mt-6 w-full max-w-[420px] shrink-0"><InlineTipComposer spotId={spotId} onPosted={onPosted} autoFocus={false} compact draftKey={`spot-comment:${spotId ?? "unknown"}`} /></div>
  </section>;
}

function ThreadRow({ thread, spotId, onPosted }: { thread: CommentThread; spotId?: string; onPosted?: (tip?: TipItem) => void }) {
  const [replying, setReplying] = useState(false);
  const { comment, replies } = thread;
  const parentTipId = comment.kind === "tip" ? comment.id.replace(/^tip:/, "") : undefined;

  return <article className="min-w-0">
    <CommentRow post={comment} onChanged={() => onPosted?.()} />
    {replies.length > 0 && <div className="relative ml-8 mt-4 space-y-4 pl-6 lg:ml-11 lg:pl-7">
      {/* Reddit-style thread line: a hairline rail (line-soft, finer than the
          old border) that curves into each reply via a small rounded elbow. */}
      <span aria-hidden className="pointer-events-none absolute left-0 top-0 bottom-5 w-px bg-line-soft" />
      {replies.map(reply => <div key={reply.id} className="relative">
        <span aria-hidden className="pointer-events-none absolute -left-6 top-0 h-[15px] w-[18px] rounded-bl-card border-b border-l border-line-soft lg:-left-7 lg:w-[22px]" />
        <CommentRow post={reply} compact onChanged={() => onPosted?.()} />
      </div>)}
    </div>}
    <div className="ml-8 mt-2 lg:ml-11">
      {replying ? <div className="mt-2 max-w-[420px]"><InlineTipComposer spotId={spotId} parentId={parentTipId} replyToName={comment.authorName} onPosted={(tip) => { onPosted?.(tip); setReplying(false); }} onCancel={() => setReplying(false)} /></div> : <button type="button" onClick={() => setReplying(true)} className="min-h-11 text-caption font-medium text-muted transition-colors hover:text-ink">Antworten</button>}
    </div>
  </article>;
}

/** A single comment: avatar, name, text, and the actions that belong to the
 *  reader looking at it. The author gets edit and delete, everyone else gets
 *  report — the same split people know from every social feed.
 *
 *  Deleting asks once, inline, rather than through a browser dialog: a native
 *  `confirm()` cannot be styled, cannot be dismissed by tapping away, and on
 *  iOS takes the page's scroll position with it. Editing happens in place, so
 *  the comment never leaves the thread it belongs to.
 */
function CommentRow({ post, compact = false, onChanged }: { post: FeedPost; compact?: boolean; onChanged?: () => void }) {
  const anonymous = !post.authorName || post.authorName === "Anonym";
  const rawId = post.id.replace(/^(tip|rating):/, "");
  const isComment = post.kind === "tip";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(post.text ?? "");
  const [confirming, setConfirming] = useState(false);
  const [reported, setReported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      after?.();
      onChanged?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Das hat nicht geklappt. Bitte versuche es erneut.");
    } finally {
      setBusy(false);
    }
  };

  const action = "min-h-10 text-caption font-medium text-muted transition-colors hover:text-ink disabled:opacity-50";

  return <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-3">
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-full text-caption font-semibold ${compact ? "h-7 w-7" : "h-9 w-9"} ${anonymous ? "bg-band text-muted" : "text-white"}`} style={anonymous ? undefined : { backgroundColor: avatarColor(post.authorName) }}>{anonymous ? "?" : initials(post.authorName)}</span>
    <div className={`flex min-w-0 items-center ${compact ? "min-h-7" : "min-h-9"}`}>
      <strong className="truncate text-ui font-semibold text-ink">{post.authorName || "Anonym"}</strong>
    </div>
    <div aria-hidden />
    <div className="min-w-0 pt-2">
      {editing ? (
        <form
          className="max-w-[420px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!draft.trim()) return;
            void run(() => editOwnTip(rawId, { body: draft }), () => setEditing(false));
          }}
        >
          <label className="sr-only" htmlFor={`edit-${rawId}`}>Kommentar bearbeiten</label>
          <textarea
            id={`edit-${rawId}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={4000}
            rows={3}
            autoFocus
            className="comment-field w-full resize-none rounded-card border border-line bg-page p-3 text-ui text-ink focus:border-ink focus:outline-none"
          />
          <div className="mt-1 flex items-center gap-4">
            <button type="submit" disabled={busy || !draft.trim()} className="min-h-10 text-caption font-semibold text-accent disabled:opacity-50">Speichern</button>
            <button type="button" disabled={busy} onClick={() => { setDraft(post.text ?? ""); setEditing(false); setError(null); }} className={action}>Abbrechen</button>
          </div>
        </form>
      ) : (
        <>
          {post.title && <span className="mb-1 block text-ui font-semibold text-ink">{post.title}</span>}
          <p className="whitespace-pre-line text-ui leading-relaxed text-ink-soft">{post.text}</p>
        </>
      )}
      <div className="mt-1 flex min-h-10 flex-wrap items-center gap-x-3 text-caption text-muted">
        <time dateTime={post.createdAt}>{relativeTime(post.createdAt)}</time>
        {post.editedAt && (
          <span title={`Bearbeitet ${relativeTime(post.editedAt)}`}>bearbeitet</span>
        )}
        {post.kind !== "photo" && <UpvoteButton kind={post.kind} id={rawId} count={post.upvotes} active={post.viewerUpvoted} />}
        {isComment && post.viewerIsAuthor && !editing && (
          confirming ? (
            <>
              <span className="text-ink">Wirklich löschen?</span>
              <button type="button" disabled={busy} onClick={() => void run(() => deleteOwnTip(rawId))} className="min-h-10 text-caption font-semibold text-danger disabled:opacity-50">Ja, löschen</button>
              <button type="button" disabled={busy} onClick={() => setConfirming(false)} className={action}>Abbrechen</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => { setDraft(post.text ?? ""); setEditing(true); }} className={action}>Bearbeiten</button>
              <button type="button" onClick={() => { setConfirming(true); setError(null); }} className={action}>Löschen</button>
            </>
          )
        )}
        {isComment && !post.viewerIsAuthor && (
          reported
            ? <span>gemeldet</span>
            : <button type="button" disabled={busy} onClick={() => void run(() => reportTip(rawId), () => setReported(true))} className={action}>Melden</button>
        )}
      </div>
      {error && <p role="alert" className="text-caption text-danger">{error}</p>}
    </div>
  </div>;
}

function CommentSkeleton() { return <div role="status" aria-live="polite" className="space-y-7 py-2"><span className="sr-only">Kommentare werden geladen</span><div aria-hidden className="h-16 animate-pulse rounded-card bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-card bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-card bg-band"/></div>; }
