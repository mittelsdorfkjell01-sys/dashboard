// Pure logic behind the gallery manager: drag order and removal confirmation.

import type { GalleryImage } from "./api";

/**
 * Reorder `items` by moving the entry at `from` to `to`.
 *
 * A pure array move rather than a full drag-and-drop implementation, so the
 * behaviour is testable without a DOM and the component only wires pointer
 * events to it.
 */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (
    from === to ||
    from < 0 ||
    to < 0 ||
    from >= items.length ||
    to >= items.length
  ) {
    return items;
  }
  const next = items.slice();
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Whether removing this image needs a confirmation step. */
export function removalNeedsConfirmation(image: GalleryImage): boolean {
  // A community photo carries a consent record; removing it should be a
  // deliberate choice, not a misclick — everything else is stock material an
  // operator can freely swap out.
  return image.provider === "community" || image.source === "user_upload";
}
