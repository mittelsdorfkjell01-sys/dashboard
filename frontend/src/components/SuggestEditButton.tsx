import { useEffect, useId, useRef, useState, type FocusEvent, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { ApiError, postSubmission } from "../lib/api";
import { CloseIcon, PencilIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import { Button, Field, Input, Select, Textarea } from "./ui";
import { useFocusTrap } from "../lib/useFocusTrap";
import { useVisualViewportBox } from "../lib/useVisualViewportBox";
import { SPOT_EDIT_TARGETS, spotEditTargetLabel } from "../lib/spotEditTargets";
import type { Spot } from "../lib/types";

// The backend's bounds for the message (app/community/service.py).
const MIN_MESSAGE = 3;
const MAX_MESSAGE = 2000;

/**
 * "Änderung vorschlagen" — lets any visitor propose a correction to one area
 * of the spot page. Posts through the generic `/submissions` review endpoint
 * (payload tagged `spot_edit_suggestion`), the same admin queue new-spot
 * submissions land in.
 *
 * Phone: a sheet from the bottom edge, like the comment menu. Desktop: a
 * centred dialog. Either way the overlay follows the *visual* viewport, so the
 * soft keyboard shrinks the card instead of covering it: the fields scroll
 * inside, and the action row stays pinned to the card's bottom edge — the
 * submit button is never behind the keyboard.
 */
export default function SuggestEditButton({ spot }: { spot: Spot }) {
  const { user } = useAuth();
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(SPOT_EDIT_TARGETS[0].key);
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  useFocusTrap(open, cardRef);
  const box = useVisualViewportBox(open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    window.addEventListener("keydown", onKey);
    // The page behind must not scroll along with the sheet.
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [open]);

  function close() {
    setOpen(false);
    // Reset after the dialog is gone, so it doesn't flash empty on close.
    window.setTimeout(() => {
      setDone(false);
      setError(null);
      setMessage("");
      setTarget(SPOT_EDIT_TARGETS[0].key);
    }, 200);
  }
  const closeRef = useRef(close);
  closeRef.current = close;

  // The card shrinks when the keyboard opens; bring the focused field back
  // into view once the viewport has settled.
  const keepFocusedVisible = (event: FocusEvent<HTMLFormElement>) => {
    const field = event.target as HTMLElement;
    window.setTimeout(() => field.scrollIntoView({ block: "nearest" }), 300);
  };

  const trimmed = message.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < MIN_MESSAGE;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (website) return; // honeypot
    if (trimmed.length < MIN_MESSAGE) return setError("Bitte beschreibe kurz die Änderung.");
    setBusy(true);
    setError(null);
    try {
      await postSubmission({
        payload: {
          kind: "spot_edit_suggestion",
          spot_id: spot.uuid ?? spot.id,
          spot_name: spot.name,
          field: target,
          field_label: spotEditTargetLabel(target),
          message: trimmed,
        },
        // A signed-in visitor is credited through their account.
        submitter_name: user ? user.displayName || undefined : name.trim() || undefined,
        submitter_email: user ? undefined : email.trim() || undefined,
        website,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Senden fehlgeschlagen. Bitte versuche es noch einmal.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Änderung vorschlagen"
        title="Änderung vorschlagen"
        className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink transition-colors hover:bg-band active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <PencilIcon className="text-lead" />
      </button>

      {open &&
        createPortal(
          <div
            className="fixed inset-x-0 top-0 z-sheet flex h-full flex-col justify-end bg-ink/30 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-[calc(0.75rem+env(safe-area-inset-top))] sm:items-center sm:justify-center sm:p-4"
            style={box ? { top: box.top, height: box.height } : undefined}
            onClick={close}
          >
            <div
              ref={cardRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              tabIndex={-1}
              onClick={(e) => e.stopPropagation()}
              data-lenis-prevent
              className="flex max-h-full w-full min-h-0 flex-col overflow-hidden rounded-card bg-surface shadow-float outline-none sm:max-w-md"
            >
              <div className="flex shrink-0 items-start justify-between gap-3 px-5 pt-4 sm:px-6 sm:pt-5">
                <div className="min-w-0 pt-2">
                  <h2 id={titleId} className="text-title font-semibold text-ink">Änderung vorschlagen</h2>
                  <p className="mt-0.5 truncate text-ui text-muted">{spot.name}</p>
                </div>
                <button
                  type="button"
                  onClick={close}
                  aria-label="Schließen"
                  className="-mr-2 grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink transition-colors hover:bg-band"
                >
                  <CloseIcon width={16} height={16} />
                </button>
              </div>

              {done ? (
                <div className="px-5 pb-5 pt-3 sm:px-6 sm:pb-6">
                  <p role="status" className="text-body text-ink">
                    Danke! Dein Vorschlag ist eingegangen. Wir prüfen ihn und passen den Spot an, wenn er stimmt.
                  </p>
                  <div className="mt-5 flex justify-end">
                    <Button variant="secondary" onClick={close}>Schließen</Button>
                  </div>
                </div>
              ) : (
                <form onSubmit={submit} onFocus={keepFocusedVisible} className="flex min-h-0 flex-1 flex-col" noValidate>
                  <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-5 pb-5 pt-3 sm:px-6">
                    <p className="text-ui text-muted">
                      Stimmt etwas nicht oder fehlt eine Info? Wähle den Bereich und beschreibe, was sich ändern sollte. Wir prüfen jeden Vorschlag, bevor er auf die Seite kommt.
                    </p>

                    <Field label="Welcher Bereich?">
                      <Select value={target} onChange={(e) => setTarget(e.target.value)}>
                        {SPOT_EDIT_TARGETS.map((t) => (
                          <option key={t.key} value={t.key}>
                            {t.label}
                          </option>
                        ))}
                      </Select>
                    </Field>

                    <Field
                      label="Deine Änderung"
                      required
                      hint={`${trimmed.length} / ${MAX_MESSAGE} Zeichen`}
                      error={tooShort ? `Mindestens ${MIN_MESSAGE} Zeichen.` : undefined}
                    >
                      <Textarea
                        required
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Was sollte geändert oder ergänzt werden?"
                        maxLength={MAX_MESSAGE}
                        rows={4}
                        className="resize-y"
                      />
                    </Field>

                    {user ? (
                      <p className="text-caption text-muted">
                        Du sendest als {user.displayName || "angemeldete Person"}. Der Vorschlag wird deinem Konto zugeordnet.
                      </p>
                    ) : (
                      <div className="grid gap-4 sm:grid-cols-2">
                        <Field label="Name (optional)">
                          <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" enterKeyHint="next" />
                        </Field>
                        <Field label="E-Mail (optional)" hint="Nur für Rückfragen zu deinem Vorschlag.">
                          <Input
                            type="email"
                            inputMode="email"
                            autoComplete="email"
                            enterKeyHint="send"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                          />
                        </Field>
                      </div>
                    )}

                    {/* Honeypot */}
                    <input
                      type="text"
                      value={website}
                      onChange={(e) => setWebsite(e.target.value)}
                      tabIndex={-1}
                      autoComplete="off"
                      aria-hidden="true"
                      className="absolute left-[-9999px] h-0 w-0 opacity-0"
                    />

                    {error && <p role="alert" className="text-ui text-danger">{error}</p>}
                  </div>

                  {/* Pinned to the card's bottom edge, so it rides above the
                      keyboard while the fields scroll. */}
                  <div className="flex shrink-0 items-center justify-end gap-2 border-t border-line px-5 py-3 sm:px-6">
                    <Button variant="ghost" onClick={close}>Abbrechen</Button>
                    <Button type="submit" loading={busy} disabled={trimmed.length < MIN_MESSAGE}>
                      Vorschlag senden
                    </Button>
                  </div>
                </form>
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
