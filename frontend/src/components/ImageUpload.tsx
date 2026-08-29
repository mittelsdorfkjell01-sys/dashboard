import { useRef, useState } from "react";

/** Hero-image requirements — kept in one place so the disclaimer and the
 *  validation gate can never drift apart. Mirrors the generation pipeline
 *  (scripts/gen_hero.py, MAX_WIDTH = 3840). */
export const HERO_REQ = {
  minWidth: 3840,
  minHeight: 2000,
  formats: ["image/jpeg", "image/png", "image/webp"],
  formatLabel: "JPG, PNG oder WebP",
  // Generous original: the server downscales + re-encodes to AVIF/WebP on upload.
  maxBytes: 40 * 1024 * 1024, // 40 MB
};

type Result =
  | { ok: true; width: number; height: number }
  // `belowMin` marks a failure that is *only* about being under the minimum
  // resolution (too narrow / too short). The admin upload can override those
  // with a warning; hard failures (format, size in bytes, portrait) never set it.
  | { ok: false; reason: string; width?: number; height?: number; belowMin?: boolean };

/** Client-side hero gate, reused by the public community upload (Sprint D). */
export function validateHeroFile(file: File): Promise<Result> {
  return new Promise((resolve) => {
    if (!HERO_REQ.formats.includes(file.type)) {
      return resolve({ ok: false, reason: `Format muss ${HERO_REQ.formatLabel} sein.` });
    }
    if (file.size > HERO_REQ.maxBytes) {
      return resolve({ ok: false, reason: `Datei zu groß (max. ${Math.round(HERO_REQ.maxBytes / 1024 / 1024)} MB).` });
    }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const { naturalWidth: w, naturalHeight: h } = img;
      if (h >= w)
        return resolve({ ok: false, width: w, height: h, reason: `Querformat erforderlich (aktuell ${w}×${h} px).` });
      if (w < HERO_REQ.minWidth)
        return resolve({ ok: false, width: w, height: h, belowMin: true, reason: `Zu klein: ${w}×${h} px — empfohlen sind mindestens ${HERO_REQ.minWidth} px Breite.` });
      if (h < HERO_REQ.minHeight)
        return resolve({ ok: false, width: w, height: h, belowMin: true, reason: `Zu niedrig: ${w}×${h} px — empfohlen sind mindestens ${HERO_REQ.minHeight} px Höhe.` });
      resolve({ ok: true, width: w, height: h });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve({ ok: false, reason: "Bild konnte nicht gelesen werden." });
    };
    img.src = url;
  });
}

/** Admin image field: shows the size disclaimer and lets a file through the
 *  gate when it satisfies HERO_REQ. With `allowBelowMin`, a below-minimum image
 *  is still accepted — but a warning disclaimer is shown that it may look blurry
 *  on large screens. `onAccept` fires with the accepted file. */
export default function ImageUpload({
  onAccept,
  allowBelowMin = false,
}: {
  onAccept?: (file: File) => void;
  /** Admin-only: accept below-minimum-resolution images with a warning. */
  allowBelowMin?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  // Accepted when it passes the gate outright, or when it only fails on
  // resolution and the caller allows below-minimum images.
  const isAccepted = (res: Result) =>
    res.ok || (allowBelowMin && !res.ok && !!res.belowMin);

  const handleFile = async (file?: File | null) => {
    setPreview((p) => {
      if (p) URL.revokeObjectURL(p);
      return null;
    });
    setResult(null);
    setFileName(null);
    if (!file) return;

    const res = await validateHeroFile(file);
    setResult(res);
    setFileName(file.name);
    if (isAccepted(res)) {
      setPreview(URL.createObjectURL(file));
      onAccept?.(file);
    }
  };

  return (
    <div className="rounded-2xl bg-[#F1F5FA] p-6">
      {/* Disclaimer */}
      <div className="rounded-xl bg-ink/5 p-4 text-label leading-relaxed text-ink-soft">
        <p className="font-semibold text-ink">Anforderungen an das Header-Bild</p>
        <ul className="mt-2 space-y-1">
          <li>• Mindestbreite <strong>{HERO_REQ.minWidth} px</strong> (für Retina-/4K-Displays, damit nichts hochskaliert wird)</li>
          <li>• Mindesthöhe {HERO_REQ.minHeight} px, <strong>Querformat</strong></li>
          <li>• Format {HERO_REQ.formatLabel}, unkomprimiertes Original bevorzugt</li>
          <li>• Max. {Math.round(HERO_REQ.maxBytes / 1024 / 1024)} MB</li>
        </ul>
        <p className="mt-2 text-muted">
          {allowBelowMin ? (
            <>
              Kleinere Bilder können <strong>trotzdem hochgeladen</strong> werden — sie
              erscheinen dann ggf. unscharf auf großen Bildschirmen.
            </>
          ) : (
            <>
              Kleinere Bilder werden <strong>abgelehnt</strong> — der Upload ist erst nach
              erfüllter Anforderung möglich.
            </>
          )}
        </p>
      </div>

      {/* Dropzone / picker */}
      <div className="mt-4">
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex w-full flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-teal/30 bg-surface px-4 py-8 text-center transition-colors hover:border-teal/50 hover:bg-teal/[0.04]"
        >
          <span className="text-ui font-medium text-teal">Bild auswählen</span>
          <span className="text-caption text-muted">JPG/PNG · min. {HERO_REQ.minWidth}px breit</span>
        </button>
      </div>

      {/* Feedback */}
      {result && !result.ok && !isAccepted(result) && (
        <p className="mt-3 rounded-lg bg-danger-bg px-3 py-2 text-label font-medium text-danger">
          ✕ {result.reason}
        </p>
      )}
      {result && !result.ok && isAccepted(result) && (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-label font-medium text-amber-700">
          ⚠ {result.reason} Das Bild wird verwendet, kann auf großen Bildschirmen
          aber unscharf wirken.
        </p>
      )}
      {result?.ok && (
        <p className="mt-3 rounded-lg bg-green/10 px-3 py-2 text-label font-medium text-green">
          ✓ {fileName} · {result.width}×{result.height} px — Anforderung erfüllt
        </p>
      )}
      {preview && (
        <div className="mt-3 aspect-[21/9] overflow-hidden rounded-xl bg-line">
          <img src={preview} alt="Vorschau" className="h-full w-full object-cover" />
        </div>
      )}
    </div>
  );
}
