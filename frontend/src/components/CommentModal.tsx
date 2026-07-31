import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ApiError, postTip } from "../lib/api";
import { CloseIcon } from "../lib/icons";

/**
 * Central comment composer, shown after the auth choice (anonym / angemeldet).
 * The page behind it is lightly dimmed and blurred. Posts through the text-only
 * tips endpoint under the chosen author name, carrying parentId for replies.
 */
export default function CommentModal({
  open,
  spotId,
  parentId,
  replyToName,
  authorName,
  onPosted,
  onClose,
}: {
  open: boolean;
  spotId?: string;
  parentId?: string;
  replyToName?: string;
  /** The resolved author name (display name when signed in, else "Anonym"). */
  authorName: string;
  onPosted?: () => void;
  onClose: () => void;
}) {
  const reduce = useReducedMotion();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset the field whenever the modal (re)opens.
  useEffect(() => {
    if (open) {
      setText("");
      setError(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const submit = async () => {
    if (!spotId || !text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await postTip(spotId, { body: text.trim(), author_name: authorName, parent_id: parentId });
      onPosted?.();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Senden fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[1200] grid place-items-center bg-black/25 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.2 }}
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Kommentar verfassen"
            className="w-full max-w-[560px] rounded-3xl bg-white p-7 shadow-float sm:p-8"
            onClick={(e) => e.stopPropagation()}
            initial={reduce ? false : { opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: reduce ? 0 : 0.22, ease: "easeOut" }}
          >
            <h2 className="text-title font-semibold text-teal">Kommentar verfassen</h2>
            {replyToName ? (
              <p className="mt-1 text-label text-muted">Antwort an {replyToName}</p>
            ) : (
              <p className="mt-1 text-label text-muted">
                als {authorName === "Anonym" ? "Anonym" : authorName}
              </p>
            )}

            <textarea
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="verfasse einen Kommentar…"
              className="comment-field mt-4 min-h-[140px] w-full resize-none rounded-2xl border-[0.5px] border-line bg-white p-4 text-body text-ink placeholder:text-muted focus:border-teal focus:outline-none focus:ring-0"
            />
            {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center gap-1.5 text-label font-medium text-muted transition-colors hover:text-ink"
              >
                <CloseIcon width={15} height={15} />
                abbrechen
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={busy || !text.trim()}
                className="rounded-2xl bg-teal px-5 py-2 text-label font-medium text-white transition-colors hover:bg-teal-hover disabled:opacity-40"
              >
                {busy ? "Senden…" : "absenden"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
