import type { RefObject } from "react";
import { avatarColor, initials, type FeedPost } from "../lib/communityFeed";

/**
 * The Info tab's single-comment teaser tile (Figma Frame_9) — one representative
 * community post (rating or tip, whichever is most recent), with a "mehr" link
 * that opens the full comments overlay (Frame_11). Also reused, one per card,
 * inside that overlay itself. "Antworte" / "Verfasse Kommentar / Tipp" are
 * intentionally inert for now — that flow lands separately (TODO).
 */
export default function SpotCommentTeaser({
  post,
  onOpenMore,
  onCompose,
  moreButtonRef,
}: {
  post: FeedPost | null;
  onOpenMore: () => void;
  /** Empty-state "Verfassen" → open the composer directly. */
  onCompose: () => void;
  /** So the overlay can return focus here on close (Info-tab teaser only). */
  moreButtonRef?: RefObject<HTMLButtonElement>;
}) {
  // No comment yet: a dashed "write the first one" prompt instead of a blank
  // gap — the default for every spot nobody has commented on.
  if (!post) {
    return (
      <div className="grid place-items-center rounded-3xl border border-dashed border-line bg-band/40 px-6 py-10 text-center">
        <p className="max-w-[26ch] text-body text-ink-soft">
          Schreibe einen Kommentar und einen Tipp für den Spot
        </p>
        <button
          ref={moreButtonRef}
          type="button"
          onClick={onCompose}
          className="mt-4 inline-flex items-center rounded-full bg-teal px-5 py-2.5 text-label font-medium text-white transition-colors hover:bg-teal-hover"
        >
          Verfassen
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-3xl bg-band p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-label font-semibold text-white"
            style={{ backgroundColor: avatarColor(post.authorName) }}
          >
            {initials(post.authorName)}
          </span>
          <span className="text-ui font-medium text-ink">{post.authorName}</span>
        </div>
        <button
          ref={moreButtonRef}
          type="button"
          onClick={onOpenMore}
          className="text-label font-medium text-teal hover:text-teal-hover"
        >
          mehr
        </button>
      </div>

      {post.text && <p className="mt-3 text-body text-ink-soft">{post.text}</p>}

      <div className="mt-5 flex items-center justify-between gap-3 text-label font-medium text-teal">
        {/* TODO: no reply/composer flow yet — placement only, per spec */}
        <button type="button" className="hover:text-teal-hover">
          Antworte
        </button>
        <button type="button" className="hover:text-teal-hover">
          Verfasse Kommentar / Tipp
        </button>
      </div>
    </div>
  );
}
