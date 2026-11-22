import type { MapPoiCategory } from "../../lib/api";
import { POI_LABEL_ZOOM, POI_META } from "./poiMeta";

export interface Box { left: number; top: number; right: number; bottom: number }

export interface PoiCandidate {
  id: string;
  category: MapPoiCategory;
  name: string | null;
  distance: number;
  /** Screen position of the coordinate, in CSS pixels. */
  x: number;
  y: number;
}

export interface PoiPlacement { visible: boolean; label: boolean }

/** The drawn icon is 22px, as on Apple's standard map; the box keeps a few
 *  pixels of air around it, so neighbouring pins never touch. */
const PIN_BOX = 28;
const LABEL_HEIGHT = 28;
const LABEL_MAX_WIDTH = 110;

export function labelWidth(name: string | null): number {
  if (!name) return 0;
  return Math.min(LABEL_MAX_WIDTH, Math.round(name.length * 6) + 6);
}

const overlaps = (a: Box, b: Box) =>
  a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;

/**
 * Greedy placement in priority order: the selected pin, then category
 * (surf school → parking → camping → café → bar), then distance from the spot.
 * A pin that would touch one already placed — or the spot pin, or the rider's
 * own position — is left out rather than stacked; a name is dropped before
 * its pin. Pure, so it can be tested without a map.
 */
export function layoutPois(
  candidates: PoiCandidate[],
  options: { zoom: number; width: number; height: number; selectedId?: string | null; reserved?: Box[] },
): Map<string, PoiPlacement> {
  const { zoom, width, height, selectedId = null, reserved = [] } = options;
  const result = new Map<string, PoiPlacement>();
  const placed: Box[] = [...reserved];
  const wantsLabels = zoom >= POI_LABEL_ZOOM;
  const ordered = [...candidates].sort((a, b) =>
    Number(b.id === selectedId) - Number(a.id === selectedId)
    || POI_META[a.category].priority - POI_META[b.category].priority
    || a.distance - b.distance
    || a.id.localeCompare(b.id));

  for (const poi of ordered) {
    const selected = poi.id === selectedId;
    const inZoom = selected || zoom >= POI_META[poi.category].minZoom;
    const onScreen = poi.x > -PIN_BOX && poi.y > -PIN_BOX && poi.x < width + PIN_BOX && poi.y < height + PIN_BOX;
    if (!inZoom || !onScreen) {
      result.set(poi.id, { visible: false, label: false });
      continue;
    }
    const half = PIN_BOX / 2;
    const pin: Box = { left: poi.x - half, top: poi.y - half, right: poi.x + half, bottom: poi.y + half };
    if (!selected && placed.some((box) => overlaps(pin, box))) {
      result.set(poi.id, { visible: false, label: false });
      continue;
    }
    placed.push(pin);
    const textWidth = wantsLabels ? labelWidth(poi.name) : 0;
    let label = false;
    if (textWidth > 0) {
      const box: Box = {
        left: poi.x - textWidth / 2,
        top: pin.bottom - 2,
        right: poi.x + textWidth / 2,
        bottom: pin.bottom - 2 + LABEL_HEIGHT,
      };
      if (selected || !placed.some((other) => other !== pin && overlaps(box, other))) {
        placed.push(box);
        label = true;
      }
    }
    result.set(poi.id, { visible: true, label });
  }
  return result;
}
