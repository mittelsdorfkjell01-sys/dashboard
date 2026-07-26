import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { avatarColor, initials, type FeedPost } from "../lib/communityFeed";
import { PlusIcon } from "../lib/icons";
import { Composer } from "./SpotCommunity";
import OverlayPanel from "./OverlayPanel";

/**
 * Kommentare overlay (Figma Frame_11) — title left, subtitle right, the spot's
 * comment tiles in a responsive grid. Each tile keeps a fixed base height; a
 * long comment is clipped with a "mehr" link that expands that one tile
 * downward (and "weniger" collapses it). A round "+" FAB bottom-right opens the
 * composer to add a comment. Triggered only by the teaser tile's "mehr" link.
 */
export default function CommentsOverlay({
  open,
  onClose,
  triggerRef,
  posts,
  spotId,
  spotName,
  onReload,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  posts: FeedPost[];
  spotId?: string;
  spotName?: string;
  /** Refetch the feed after a new comment is posted. */
  onReload?: () => void;
}) {
  const [composerOpen, setComposerOpen] = useState(false);

  useEffect(() => {
    if (!open) setComposerOpen(false);
  }, [open]);

  const comments = posts.filter((p) => p.text);

  return (
    <OverlayPanel open={open} onClose={onClose} triggerRef={triggerRef}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-editorial-2 font-semibold text-ink">Kommentare</h2>
        <p className="text-body text-muted">Kommentare und Tipps aus der Community</p>
      </div>

      {composerOpen && spotId && (
        <div className="mt-6">
          <Composer
            spotId={spotId}
            spotName={spotName ?? ""}
            onPosted={() => {
              onReload?.();
              setComposerOpen(false);
            }}
          />
        </div>
      )}

      {comments.length === 0 ? (
        <p className="mt-8 text-body text-muted">Noch keine Kommentare oder Tipps — sei die/der Erste.</p>
      ) : (
        <div className="mt-8 grid items-start gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {comments.map((post) => (
            <CommentCard key={post.id} post={post} />
          ))}
        </div>
      )}

      {/* Round "+" compose FAB, bottom-right of the panel — hidden while the
          composer is open (it has its own controls). */}
      {!composerOpen && (
        <button
          type="button"
          onClick={() => setComposerOpen(true)}
          aria-label="Kommentar verfassen"
          className="fixed bottom-6 right-6 z-[1102] grid h-14 w-14 place-items-center rounded-full bg-teal text-white shadow-lg transition-colors hover:bg-teal-hover sm:bottom-8 sm:right-8"
        >
          <PlusIcon className="text-[26px]" />
        </button>
      )}
    </OverlayPanel>
  );
}

/**
 * One comment tile. Fixed base height (`min-h`); the comment text fills the
 * remaining space and is clipped when it doesn't fit — a "mehr" link then
 * expands this tile to its full height ("weniger" collapses it). "Antworte"
 * stays pinned at the bottom. The overflow check runs only while collapsed, so
 * the toggle doesn't vanish once expanded.
 */
function CommentCard({ post }: { post: FeedPost }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (expanded) return; // keep the last measurement while open
    const el = boxRef.current;
    if (!el) return;
    const check = () => setOverflowing(el.scrollHeight - el.clientHeight > 1);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [expanded, post.text]);

  return (
    <div className="flex min-h-[360px] flex-col rounded-3xl bg-band p-6">
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-label font-semibold text-white"
          style={{ backgroundColor: avatarColor(post.authorName) }}
        >
          {initials(post.authorName)}
        </span>
        <span className="text-ui font-medium text-ink">{post.authorName}</span>
      </div>

      <div ref={boxRef} className={`relative mt-4 ${expanded ? "" : "flex-1 overflow-hidden"}`}>
        <p className="whitespace-pre-line text-body text-ink-soft">{post.text}</p>
        {!expanded && overflowing && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-band to-transparent" />
        )}
      </div>

      {overflowing && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 self-start text-label font-medium text-teal hover:text-teal-hover"
        >
          {expanded ? "weniger" : "mehr"}
        </button>
      )}

      <div className="mt-5 flex items-center gap-3 text-label font-medium text-teal">
        {/* TODO: reply flow lands separately — placement only, per spec */}
        <button type="button" className="underline-offset-2 hover:underline">
          Antworte
        </button>
      </div>
    </div>
  );
}
