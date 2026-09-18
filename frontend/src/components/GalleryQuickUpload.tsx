import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, getImageLicense, uploadSpotImage } from "../lib/api";
import { CloseIcon } from "../lib/icons";
import { Button } from "./ui";

export interface GalleryQuickUploadHandle {
  /** Opens the phone's native photo picker. Call it inside a tap handler so iOS
   *  treats it as a trusted user gesture. */
  openPicker: () => void;
}

/**
 * Mobile-native gallery upload. The trigger opens the phone's photo picker
 * straight away; once a photo is chosen a compact bottom-sheet shows just the
 * preview and the (legally required) rights confirmation + upload — no
 * desktop-style form with credit fields. Uploads land in the admin review queue.
 */
export const GalleryQuickUpload = forwardRef<GalleryQuickUploadHandle, {
  spotId: string;
  onUploaded?: () => void;
}>(function GalleryQuickUpload({ spotId, onUploaded }, ref) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [terms, setTerms] = useState<{ version: string; terms: string } | null>(null);
  const [showTerms, setShowTerms] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot

  useImperativeHandle(ref, () => ({ openPicker: () => inputRef.current?.click() }), []);
  useEffect(() => {
    getImageLicense().then(setTerms).catch(() => {});
  }, []);

  const setPicked = (f: File | null) => {
    setPreview((p) => {
      if (p) URL.revokeObjectURL(p);
      return f ? URL.createObjectURL(f) : null;
    });
    setFile(f);
    setAccepted(false);
    setError(null);
    setNotice(null);
    // Let the same file be re-picked after a cancel (Chrome keeps the value).
    if (inputRef.current) inputRef.current.value = "";
  };
  const close = () => {
    setPicked(null);
    setShowTerms(false);
  };

  const submit = async () => {
    if (!file || !accepted || website) return;
    setBusy(true);
    setError(null);
    try {
      await uploadSpotImage(spotId, file, "gallery", { licenseAccept: accepted, review: true });
      setNotice("Danke! Dein Bild wartet auf Freigabe.");
      window.setTimeout(() => {
        close();
        onUploaded?.();
      }, 1600);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!file) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);

  // Portal everything to <body>: while the gallery overlay is open it marks
  // #root inert, and a hidden input inside an inert subtree can't be opened via
  // .click(). At body level the picker always opens.
  return createPortal(
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => setPicked(e.target.files?.[0] ?? null)}
      />
      {file && (
          <div
            className="fixed inset-0 z-[1300] grid place-items-end bg-black/40 sm:place-items-center sm:p-4"
            onClick={close}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Bild hinzufügen"
              onClick={(e) => e.stopPropagation()}
              data-lenis-prevent
              className="w-full rounded-t-3xl bg-surface p-5 shadow-float sm:max-w-md sm:rounded-[14px] sm:p-6"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sz-18 font-semibold text-ink">Bild hinzufügen</p>
                <button
                  type="button"
                  onClick={close}
                  aria-label="Abbrechen"
                  className="grid h-9 w-9 place-items-center rounded-full text-ink transition-colors hover:bg-band"
                >
                  <CloseIcon width={16} height={16} />
                </button>
              </div>

              {preview && (
                <div className="mt-4 overflow-hidden rounded-[14px] bg-band">
                  <img src={preview} alt="" className="aspect-[4/3] w-full object-cover" />
                </div>
              )}

              <label className="mt-4 flex items-start gap-2.5 text-label text-ink">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                  className="mt-0.5 h-4 w-4 accent-ink"
                />
                <span>
                  Ich habe die Rechte am Bild und bestätige die{" "}
                  <button
                    type="button"
                    onClick={() => setShowTerms((v) => !v)}
                    className="underline underline-offset-2"
                  >
                    Rechte- &amp; Einwilligungserklärung{terms ? ` (${terms.version})` : ""}
                  </button>
                  .
                </span>
              </label>
              {showTerms && terms && (
                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-[14px] bg-band p-3 text-caption text-ink-soft">
                  {terms.terms}
                </pre>
              )}

              {/* Honeypot — real people never fill this. */}
              <input
                type="text"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                tabIndex={-1}
                autoComplete="off"
                aria-hidden="true"
                className="hidden"
              />

              {error && <p role="alert" className="mt-3 text-label text-danger">{error}</p>}
              {notice && <p role="status" className="mt-3 text-label text-green">{notice}</p>}

              <div className="mt-5 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={close}
                  className="min-h-11 px-3 text-label font-medium text-ink transition-opacity hover:opacity-70"
                >
                  Abbrechen
                </button>
                <Button type="button" onClick={submit} disabled={busy || !accepted}>
                  {busy ? "Hochladen…" : "Hochladen"}
                </Button>
              </div>
            </div>
          </div>
      )}
    </>,
    document.body
  );
});
