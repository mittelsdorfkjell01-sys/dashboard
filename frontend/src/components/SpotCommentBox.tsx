import { useEffect, useRef, useState } from "react";
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
export default function SpotCommentBox({ spotId, posts, onPosted, onRemoved, onEdited, loading = false, error = null }: { spotId?: string; posts: FeedPost[]; onPosted?: (tip?: TipItem) => void; onRemoved?: (id: string) => void; onEdited?: (tip: TipItem) => void; loading?: boolean; error?: string | null }) {
  const threads = commentThreads(posts);
  const [visible, setVisible] = useState(INITIAL_VISIBLE);
  const shown = threads.slice(0, visible);

  return <section aria-labelledby="spot-comments-title" className="flex min-w-0 flex-col lg:h-full">
    <h2 id="spot-comments-title" className="text-ui font-semibold text-ink">Kommentare</h2>
    <div className="min-h-0 flex-1 lg:mt-2 lg:overflow-y-auto lg:pr-2">
      <div className="mt-7 lg:mt-2">
        {loading && threads.length === 0 ? <CommentSkeleton /> : error && threads.length === 0 ? <div role="alert" className="py-8 text-body text-muted">Kommentare konnten nicht geladen werden. <button type="button" onClick={() => onPosted?.()} className="font-medium text-accent underline">Erneut versuchen</button></div> : threads.length === 0 ? <div className="py-8"><p className="text-body font-semibold text-ink">Teile deine Erfahrung mit diesem Spot</p><p className="mt-2 text-ui leading-relaxed text-muted">Hilfreich sind Bedingungen, Einstieg, Gefahren oder Tipps zu ähnlichen Spots.</p></div> : <div className="space-y-7">
          {shown.map(thread => <ThreadRow key={thread.comment.id} thread={thread} spotId={spotId} onPosted={onPosted} onRemoved={onRemoved} onEdited={onEdited} />)}
        </div>}
      </div>
      {visible < threads.length && <button type="button" onClick={() => setVisible(v => v + PAGE_SIZE)} className="mt-6 min-h-11 self-start text-ui font-medium text-accent transition-colors hover:text-accent-hover">Weitere Kommentare laden ({threads.length - visible})</button>}
    </div>
    <div className="mx-auto mt-6 w-full max-w-[420px] shrink-0"><InlineTipComposer spotId={spotId} onPosted={onPosted} autoFocus={false} compact draftKey={`spot-comment:${spotId ?? "unknown"}`} /></div>
  </section>;
}

function ThreadRow({ thread, spotId, onPosted, onRemoved, onEdited }: { thread: CommentThread; spotId?: string; onPosted?: (tip?: TipItem) => void; onRemoved?: (id: string) => void; onEdited?: (tip: TipItem) => void }) {
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const { comment, replies } = thread;
  const parentTipId = comment.kind === "tip" ? comment.id.replace(/^tip:/, "") : undefined;

  // Every row offers "Antworten", and every reply lands on the thread's root —
  // the backend flattens a reply-to-a-reply onto its parent anyway, so a deeper
  // indent would promise a nesting that does not exist. Replying to someone
  // further down just addresses them by name, which is what Instagram does too.
  const composer = (name: string) => (
    <div className="ml-11 mt-2 max-w-[420px]">
      <InlineTipComposer
        spotId={spotId}
        parentId={parentTipId}
        replyToName={name}
        onPosted={(tip) => { onPosted?.(tip); setReplyTo(null); }}
        onCancel={() => setReplyTo(null)}
      />
    </div>
  );

  return <article className="min-w-0">
    <CommentRow post={comment} onChanged={() => onPosted?.()} onRemoved={onRemoved} onEdited={onEdited} onReply={() => setReplyTo(comment.authorName || "Anonym")} />
    {replyTo === (comment.authorName || "Anonym") && composer(comment.authorName || "Anonym")}
    {replies.length > 0 && <div className="relative ml-8 mt-3 space-y-3 pl-6 lg:ml-11 lg:pl-7">
      {/* Reddit-style thread line: a hairline rail (line-soft, finer than the
          old border) that curves into each reply via a small rounded elbow. */}
      <span aria-hidden className="pointer-events-none absolute left-0 top-0 bottom-5 w-px bg-line-soft" />
      {replies.map(reply => <div key={reply.id} className="relative">
        <span aria-hidden className="pointer-events-none absolute -left-6 top-0 h-[15px] w-[18px] rounded-bl-card border-b border-l border-line-soft lg:-left-7 lg:w-[22px]" />
        <CommentRow post={reply} compact onChanged={() => onPosted?.()} onRemoved={onRemoved} onEdited={onEdited} onReply={() => setReplyTo(reply.authorName || "Anonym")} />
        {replyTo === (reply.authorName || "Anonym") && composer(reply.authorName || "Anonym")}
      </div>)}
    </div>}
  </article>;
}

/** A single comment in the grammar people know from a social feed: a round
 *  avatar, the author's name running inline with what they wrote, and one
 *  small muted line of actions underneath.
 *
 *  Name and text share a paragraph rather than sitting on two lines. A short
 *  comment is the common case — "Stimmt, bei Niedrigwasser" — and giving it a
 *  headline of its own turned every one of those into a three-line block.
 *
 *  Edit, delete and report hide behind a "…" menu. They are rare, and spelling
 *  all three out under every comment made the list read as a settings screen.
 *  Reply and the vote stay visible, because those are the two things people
 *  actually come to do.
 *
 *  Deleting asks once, inline, rather than through a browser dialog: a native
 *  `confirm()` cannot be styled, cannot be dismissed by tapping away, and on
 *  iOS takes the page's scroll position with it.
 */
function CommentRow({ post, compact = false, onChanged, onRemoved, onEdited, onReply }: { post: FeedPost; compact?: boolean; onChanged?: () => void; onRemoved?: (id: string) => void; onEdited?: (tip: TipItem) => void; onReply?: () => void }) {
  const anonymous = !post.authorName || post.authorName === "Anonym";
  const rawId = post.id.replace(/^(tip|rating):/, "");
  const isComment = post.kind === "tip";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(post.text ?? "");
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [reported, setReported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

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

  const meta = "min-h-8 text-caption font-medium text-muted transition-colors hover:text-ink disabled:opacity-50";
  const menuItem = "flex w-full items-center px-3 py-2 text-left text-caption text-ink transition-colors hover:bg-band";
  const avatar = compact ? "h-7 w-7" : "h-8 w-8";

  return <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-3">
    <span aria-hidden className={`grid shrink-0 place-items-center self-start rounded-full text-caption font-semibold ${avatar} ${anonymous ? "bg-band text-muted" : "text-white"}`} style={anonymous ? undefined : { backgroundColor: avatarColor(post.authorName) }}>{anonymous ? "?" : initials(post.authorName)}</span>
    <div className="min-w-0">
      {editing ? (
        <form
          className="max-w-[420px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!draft.trim()) return;
            void run(async () => {
              const updated = await editOwnTip(rawId, { body: draft });
              onEdited?.(updated);
            }, () => setEditing(false));
          }}
        >
          <label className="sr-only" htmlFor={`edit-${rawId}`}>Kommentar bearbeiten</label>
          <textarea
            id={`edit-${rawId}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && draft.trim() && !busy) {
                e.preventDefault();
                (e.currentTarget.form as HTMLFormElement | null)?.requestSubmit();
              }
            }}
            maxLength={4000}
            rows={3}
            autoFocus
            className="comment-field w-full resize-none rounded-card border border-line bg-page p-3 text-ui text-ink focus:border-ink focus:outline-none"
          />
          <div className="mt-1 flex items-center gap-4">
            <button type="submit" disabled={busy || !draft.trim()} className="min-h-8 text-caption font-semibold text-accent disabled:opacity-50">Speichern</button>
            <button type="button" disabled={busy} onClick={() => { setDraft(post.text ?? ""); setEditing(false); setError(null); }} className={meta}>Abbrechen</button>
          </div>
        </form>
      ) : (
        <p className="whitespace-pre-line break-words text-ui leading-relaxed text-ink-soft">
          <strong className="mr-1.5 font-semibold text-ink">{post.authorName || "Anonym"}</strong>
          {post.title && <span className="mr-1.5 font-semibold text-ink">{post.title}</span>}
          {post.text}
        </p>
      )}

      <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-3">
        <time className="text-caption text-muted" dateTime={post.createdAt}>{relativeTime(post.createdAt)}</time>
        {post.editedAt && (
          <span className="text-caption text-muted" title={`Bearbeitet ${relativeTime(post.editedAt)}`}>bearbeitet</span>
        )}
        {post.kind !== "photo" && <UpvoteButton kind={post.kind} id={rawId} count={post.upvotes} active={post.viewerUpvoted} />}
        {isComment && onReply && !editing && (
          <button type="button" onClick={onReply} className={meta}>Antworten</button>
        )}
        {isComment && !editing && (
          confirming ? (
            <>
              <span className="text-caption text-ink">Wirklich löschen?</span>
              <button type="button" disabled={busy} onClick={() => void run(async () => {
                // The row goes at once; the reload behind it corrects the list
                // if the request turns out to fail.
                onRemoved?.(rawId);
                await deleteOwnTip(rawId);
              })} className="min-h-8 text-caption font-semibold text-danger disabled:opacity-50">Ja, löschen</button>
              <button type="button" disabled={busy} onClick={() => setConfirming(false)} className={meta}>Abbrechen</button>
            </>
          ) : (
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-expanded={menuOpen}
                aria-label="Weitere Aktionen"
                className={`${meta} px-1 tracking-widest`}
              >
                ···
              </button>
              {/* Anchored to the trigger's right edge: the trigger sits at the end
                  of the meta row, so a left-anchored menu ran off the column. */}
              {menuOpen && (
                <div role="menu" className="absolute right-0 top-full z-10 mt-1 min-w-[10rem] overflow-hidden rounded-card border border-line bg-surface shadow-card">
                  {post.viewerIsAuthor ? (
                    <>
                      <button type="button" role="menuitem" className={menuItem} onClick={() => { setDraft(post.text ?? ""); setEditing(true); setMenuOpen(false); }}>Bearbeiten</button>
                      <button type="button" role="menuitem" className={`${menuItem} text-danger`} onClick={() => { setConfirming(true); setMenuOpen(false); setError(null); }}>Löschen</button>
                    </>
                  ) : reported ? (
                    <span className={`${menuItem} text-muted`}>Gemeldet</span>
                  ) : (
                    <button type="button" role="menuitem" className={menuItem} disabled={busy} onClick={() => { setMenuOpen(false); void run(() => reportTip(rawId), () => setReported(true)); }}>Melden</button>
                  )}
                </div>
              )}
            </div>
          )
        )}
      </div>
      {error && <p role="alert" className="text-caption text-danger">{error}</p>}
    </div>
  </div>;
}

function CommentSkeleton() { return <div role="status" aria-live="polite" className="space-y-7 py-2"><span className="sr-only">Kommentare werden geladen</span><div aria-hidden className="h-16 animate-pulse rounded-card bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-card bg-band"/><div aria-hidden className="h-16 animate-pulse rounded-card bg-band"/></div>; }
