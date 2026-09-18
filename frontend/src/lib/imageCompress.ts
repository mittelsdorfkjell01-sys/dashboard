/**
 * Downscale + re-encode a picked photo in the browser before uploading it.
 *
 * Phones (e.g. an iPhone 13 Pro) produce 12 MP JPEGs of several megabytes, and
 * the API rejects oversized bodies with HTTP 413 ("Anfrage fehlgeschlagen").
 * Shrinking the longest edge to `maxDim` and re-encoding as JPEG keeps uploads
 * comfortably under that limit while staying visually indistinguishable in the
 * gallery. EXIF orientation is baked in (`imageOrientation: "from-image"`) so
 * portrait phone shots don't come out sideways once the metadata is dropped.
 *
 * Fully defensive: anything that can't be decoded, drawn, or shrunk below the
 * original just returns the original file, so a picked photo is never lost to a
 * compression hiccup.
 */
export async function compressImageForUpload(
  file: File,
  opts: { maxDim?: number; quality?: number } = {},
): Promise<File> {
  const maxDim = opts.maxDim ?? 2048;
  const quality = opts.quality ?? 0.82;

  if (typeof document === "undefined") return file;
  if (!/^image\/(jpe?g|png|webp)$/i.test(file.type)) return file;

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file; // undecodable here → let the server deal with the original
  }

  try {
    const { width, height } = bitmap;
    const scale = Math.min(1, maxDim / Math.max(width, height));
    const targetW = Math.max(1, Math.round(width * scale));
    const targetH = Math.max(1, Math.round(height * scale));

    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, targetW, targetH);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", quality),
    );
    if (!blob || blob.size >= file.size) return file; // no win → keep original

    const name = file.name.replace(/\.[^./\\]+$/, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg", lastModified: Date.now() });
  } finally {
    bitmap.close?.();
  }
}
