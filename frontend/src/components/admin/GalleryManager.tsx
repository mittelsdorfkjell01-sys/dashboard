// Gallery management: reorder by drag, remove, swap the hero.
//
// Same component for spots and regions — the entity type only changes which
// column the server writes to.

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getGallery,
  promoteGalleryImage,
  reorderGallery,
  removeGalleryImage,
  resolveMediaUrl,
  type GalleryImage,
} from "../../lib/api";
import type { MediaEntityType } from "../../lib/mediaPicker";
import { moveItem, removalNeedsConfirmation } from "../../lib/gallery";
import Modal from "../ui/Modal";
import { Button } from "./ui";

export default function GalleryManager({
  entityType,
  entityId,
  onHeroChanged,
}: {
  entityType: MediaEntityType;
  entityId: string;
  /** The entity's `image` changed (a gallery photo was promoted) — the caller
   *  reloads its record so the hero preview stays in sync. */
  onHeroChanged: () => void;
}) {
  const [items, setItems] = useState<GalleryImage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<GalleryImage | null>(null);
  const dragIndex = useRef<number | null>(null);

  const load = () => {
    getGallery(entityType, entityId)
      .then((res) => setItems(res.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Laden fehlgeschlagen."));
  };

  useEffect(load, [entityType, entityId]);

  const persistOrder = async (next: GalleryImage[]) => {
    setItems(next);
    try {
      const res = await reorderGallery(entityType, entityId, next.map((i) => i.id));
      setItems(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reihenfolge konnte nicht gespeichert werden.");
      load(); // reload the server's actual order
    }
  };

  const drop = (targetIndex: number) => {
    if (!items || dragIndex.current === null) return;
    const next = moveItem(items, dragIndex.current, targetIndex);
    dragIndex.current = null;
    if (next !== items) void persistOrder(next);
  };

  const remove = async (image: GalleryImage) => {
    setBusyId(image.id);
    setError(null);
    try {
      await removeGalleryImage(image.id);
      setItems((prev) => (prev ? prev.filter((i) => i.id !== image.id) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Entfernen fehlgeschlagen.");
    } finally {
      setBusyId(null);
      setConfirmRemove(null);
    }
  };

  const promote = async (image: GalleryImage) => {
    setBusyId(image.id);
    setError(null);
    try {
      await promoteGalleryImage(image.id);
      onHeroChanged();
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Konnte nicht zum Hero gemacht werden.");
    } finally {
      setBusyId(null);
    }
  };

  if (items === null) {
    return <p className="text-caption text-admin-muted">Lädt…</p>;
  }

  return (
    <div>
      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger"
        >
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <p className="text-caption text-admin-muted">Noch keine Galeriebilder.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((image, index) => (
            <li
              key={image.id}
              draggable
              onDragStart={() => {
                dragIndex.current = index;
              }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => drop(index)}
              className="group relative cursor-grab overflow-hidden rounded-lg border border-admin-border bg-admin-bg active:cursor-grabbing"
            >
              <img
                src={resolveMediaUrl(image.url)}
                alt=""
                className="aspect-[4/3] w-full object-cover"
              />
              <div className="absolute inset-x-0 bottom-0 flex justify-end gap-1 bg-gradient-to-t from-black/70 to-transparent p-1.5 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  type="button"
                  disabled={busyId === image.id}
                  onClick={() => void promote(image)}
                  title="Als Hero übernehmen"
                  className="rounded bg-white/90 px-2 py-1 text-[11px] font-medium text-black hover:bg-white disabled:opacity-50"
                >
                  Als Hero
                </button>
                <button
                  type="button"
                  disabled={busyId === image.id}
                  onClick={() =>
                    removalNeedsConfirmation(image) ? setConfirmRemove(image) : void remove(image)
                  }
                  title="Entfernen"
                  className="rounded bg-white/90 px-2 py-1 text-[11px] font-medium text-black hover:bg-white disabled:opacity-50"
                >
                  Entfernen
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={confirmRemove !== null}
        onClose={() => setConfirmRemove(null)}
        labelledBy="gallery-remove-title"
        cardClassName="max-w-md rounded-lg bg-admin-surface p-6"
      >
        <h2 id="gallery-remove-title" className="text-ui font-semibold text-admin-fg">
          Community-Foto entfernen?
        </h2>
        <p className="mt-2 text-label text-admin-fg2">
          Dieses Bild trägt einen Einwilligungsnachweis eines Community-Mitglieds.
          Entfernen ist nicht rückgängig zu machen.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmRemove(null)}>
            Abbrechen
          </Button>
          <Button
            variant="destructive"
            disabled={!!confirmRemove && busyId === confirmRemove.id}
            onClick={() => confirmRemove && void remove(confirmRemove)}
          >
            Entfernen
          </Button>
        </div>
      </Modal>
    </div>
  );
}
