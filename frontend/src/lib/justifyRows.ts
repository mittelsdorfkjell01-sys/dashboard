import type { CommunityImage } from "./api";

export interface JustifiedTile {
  photo: CommunityImage;
  /** Rendered pixel size for this tile inside its row. */
  width: number;
  height: number;
}
export type JustifiedRow = JustifiedTile[];

/** 3:2 landscape when a photo has no stored dimensions — a neutral default
 *  that keeps the row maths stable until the real ratio is known. */
const FALLBACK_RATIO = 1.5;

export const aspectRatio = (p: CommunityImage): number =>
  p.width && p.height && p.height > 0 ? p.width / p.height : FALLBACK_RATIO;

/**
 * Flickr/Google-Photos-style justified layout: pack photos into rows of equal
 * height, each photo keeping its aspect ratio, widths scaled so every full row
 * fills `containerWidth` edge-to-edge. The trailing partial row is left at
 * (roughly) the target height and left-aligned, so one or two leftover photos
 * never blow up to full width.
 *
 * Pure and deterministic — the caller measures `containerWidth` and picks a
 * `targetHeight`/`gap`; this only does arithmetic, so it's trivially testable.
 */
export function justifyRows(
  photos: CommunityImage[],
  containerWidth: number,
  targetHeight: number,
  gap: number
): JustifiedRow[] {
  if (containerWidth <= 0 || photos.length === 0) return [];

  const rows: JustifiedRow[] = [];
  let current: CommunityImage[] = [];
  let ratioSum = 0;

  const flush = (isLast: boolean) => {
    if (current.length === 0) return;
    const gaps = (current.length - 1) * gap;
    // Height that makes this row exactly fill the container width.
    let height = (containerWidth - gaps) / ratioSum;
    // Don't let a short trailing row stretch its photos oversized.
    if (isLast) height = Math.min(height, targetHeight * 1.5);
    rows.push(
      current.map((photo) => ({
        photo,
        width: aspectRatio(photo) * height,
        height,
      }))
    );
    current = [];
    ratioSum = 0;
  };

  for (const photo of photos) {
    current.push(photo);
    ratioSum += aspectRatio(photo);
    const gaps = (current.length - 1) * gap;
    // Once the row (laid out at the target height) would overflow, close it.
    if (ratioSum * targetHeight + gaps >= containerWidth) flush(false);
  }
  flush(true);

  return rows;
}
