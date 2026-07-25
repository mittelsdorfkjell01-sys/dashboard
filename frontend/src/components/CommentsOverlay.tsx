import type { RefObject } from "react";
import type { FeedPost } from "../lib/communityFeed";
import OverlayPanel from "./OverlayPanel";
import SpotCommentTeaser from "./SpotCommentTeaser";

/** Kommentare overlay (Figma Frame_11) — title left, subtitle right, up to
 *  three comment tiles side by side (never fabricated to fill the row — a
 *  spot with one comment shows one tile). Triggered only by the teaser
 *  tile's "mehr" link. */
export default function CommentsOverlay({
  open,
  onClose,
  triggerRef,
  posts,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  posts: FeedPost[];
}) {
  const featured = posts.slice(0, 3);

  return (
    <OverlayPanel open={open} onClose={onClose} triggerRef={triggerRef}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-editorial-2 font-semibold text-ink">Kommentare</h2>
        <p className="text-body text-muted">Kommentare und Tipps aus der Community</p>
      </div>

      {featured.length === 0 ? (
        <p className="mt-8 text-body text-muted">Noch keine Kommentare oder Tipps.</p>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {featured.map((post) => (
            <SpotCommentTeaser key={post.id} post={post} onOpenMore={() => {}} />
          ))}
        </div>
      )}
    </OverlayPanel>
  );
}
