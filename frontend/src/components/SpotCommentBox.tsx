import { useState, type RefObject } from "react";
import { avatarColor, initials, type FeedPost } from "../lib/communityFeed";
import InlineTipComposer from "./InlineTipComposer";

/**
 * Info-tab comment tile (Figma Frame_9, under the facilities). Shows the newest
 * comment when one exists, otherwise a "write the first one" prompt. Writing or
 * replying flips the tile into an inline compose mask ("Antworte" targets the
 * shown comment, "Verfasse Kommentar / Tipp" posts a new top-level comment).
 * "mehr" opens the full Kommentare overlay. No shadow — it separates from the
 * page by its band fill and fills the column down to the gallery's bottom.
 */
export default function SpotCommentBox({
  spotId,
  comment,
  onOpenMore,
  onPosted,
  moreButtonRef,
}: {
  spotId?: string;
  /** Newest top-level comment to feature, or null when there are none. */
  comment: FeedPost | null;
  onOpenMore: () => void;
  onPosted?: () => void;
  moreButtonRef?: RefObject<HTMLButtonElement>;
}) {
  const [compose, setCompose] = useState<{ parentId?: string; replyToName?: string } | null>(null);

  // Only a tip can be replied to (the backend parent is a local_tip).
  const replyTargetId =
    comment && comment.kind === "tip" ? comment.id.replace(/^tip:/, "") : undefined;

  const posted = () => {
    setCompose(null);
    onPosted?.();
  };

  return (
    <div className="flex flex-1 flex-col rounded-3xl bg-band p-6">
      <div className="flex items-center justify-between gap-3">
        <p className="text-label text-muted">Kommentare oder Tips</p>
        {comment && !compose && (
          <button
            ref={moreButtonRef}
            type="button"
            onClick={onOpenMore}
            className="text-label font-medium text-teal transition-colors hover:text-teal-hover"
          >
            mehr
          </button>
        )}
      </div>

      {compose ? (
        <div className="mt-4 flex min-h-0 flex-1 flex-col">
          <InlineTipComposer
            spotId={spotId}
            parentId={compose.parentId}
            replyToName={compose.replyToName}
            onPosted={posted}
            onCancel={() => setCompose(null)}
          />
        </div>
      ) : comment ? (
        <>
          <div className="mt-4 min-h-0 flex-1 overflow-hidden">
            <div className="flex items-center gap-2.5">
              <span
                aria-hidden="true"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-label font-semibold text-white"
                style={{ backgroundColor: avatarColor(comment.authorName) }}
              >
                {initials(comment.authorName)}
              </span>
              <span className="text-ui font-medium text-ink">{comment.authorName}</span>
            </div>
            <p className="mt-3 whitespace-pre-line text-body text-ink-soft">{comment.text}</p>
          </div>
          <div className="mt-4 flex items-center gap-5 text-label font-medium text-teal">
            <button
              type="button"
              onClick={() =>
                setCompose(
                  replyTargetId
                    ? { parentId: replyTargetId, replyToName: comment.authorName }
                    : {}
                )
              }
              className="transition-colors hover:text-teal-hover"
            >
              Antworte
            </button>
            <button
              type="button"
              onClick={() => setCompose({})}
              className="transition-colors hover:text-teal-hover"
            >
              Verfasse Kommentar / Tipp
            </button>
          </div>
        </>
      ) : (
        <div className="mt-4 flex min-h-0 flex-1 flex-col items-center justify-center text-center">
          <p className="max-w-[26ch] text-body text-ink-soft">
            Schreibe einen Kommentar und einen Tipp für den Spot
          </p>
          <button
            type="button"
            onClick={() => setCompose({})}
            className="mt-4 inline-flex items-center rounded-full bg-teal px-5 py-2.5 text-label font-medium text-white transition-colors hover:bg-teal-hover"
          >
            Verfassen
          </button>
        </div>
      )}
    </div>
  );
}
