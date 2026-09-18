import { useEffect, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { ApiError, postSubmission } from "../lib/api";
import { CloseIcon, PencilIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import { Button, Input, Select, Textarea } from "./ui";
import type { Spot } from "../lib/types";

/** Every editable "point" on the spot page a visitor can flag a correction for.
 *  Kept explicit (rather than free text only) so admins can triage by area. */
const EDIT_TARGETS: { key: string; label: string }[] = [
  { key: "name", label: "Name des Spots" },
  { key: "region", label: "Region / Land" },
  { key: "sports", label: "Sportarten" },
  { key: "description", label: "Beschreibung" },
  { key: "facilities", label: "Ausstattung" },
  { key: "location", label: "Lage / Karte" },
  { key: "data", label: "Spotdaten (Wind, Bedingungen …)" },
  { key: "other", label: "Sonstiges" },
];

/**
 * "Änderung vorschlagen" — lets any visitor propose a correction to a single
 * point on the spot page. There was no dedicated per-field edit-suggestion
 * feature before, so this posts through the generic `/submissions` review
 * endpoint (payload tagged `spot_edit_suggestion`) — the same admin queue that
 * new-spot submissions land in. Text button, same row as save/share; opens a
 * small modal form.
 */
export default function SuggestEditButton({ spot }: { spot: Spot }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(EDIT_TARGETS[0].key);
  const [message, setMessage] = useState("");
  const [name, setName] = useState(user?.displayName ?? "");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const close = () => {
    setOpen(false);
    // reset after the modal is gone so it doesn't flash empty on close
    window.setTimeout(() => {
      setDone(false);
      setError(null);
      setMessage("");
    }, 200);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (website) return; // honeypot
    if (!message.trim()) return setError("Bitte beschreibe kurz die Änderung.");
    setBusy(true);
    setError(null);
    try {
      const label = EDIT_TARGETS.find((t) => t.key === target)?.label ?? target;
      await postSubmission({
        payload: {
          kind: "spot_edit_suggestion",
          spot_id: spot.uuid ?? spot.id,
          spot_name: spot.name,
          field: target,
          field_label: label,
          message: message.trim(),
        },
        submitter_name: name.trim() || undefined,
        submitter_email: email.trim() || undefined,
        website,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Senden fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex min-h-10 items-center gap-2 rounded-full border border-line px-4 text-label font-medium text-ink transition-colors hover:bg-band active:scale-[0.98] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <PencilIcon className="text-sz-16" />
        Änderung vorschlagen
      </button>

      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[1300] grid place-items-center bg-black/40 p-4"
            style={{ paddingTop: "calc(1rem + env(safe-area-inset-top, 0px))" }}
            onClick={close}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Änderung vorschlagen"
              onClick={(e) => e.stopPropagation()}
              data-lenis-prevent
              className="max-h-[88vh] w-[min(94vw,460px)] overflow-y-auto rounded-[14px] bg-surface p-5 shadow-float sm:p-6"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sz-18 font-semibold text-ink">Änderung vorschlagen</p>
                <button
                  type="button"
                  onClick={close}
                  aria-label="Schließen"
                  className="grid h-9 w-9 place-items-center rounded-full text-ink transition-colors hover:bg-band"
                >
                  <CloseIcon width={16} height={16} />
                </button>
              </div>

              {done ? (
                <p role="status" className="mt-4 text-body text-green">
                  Danke! Dein Vorschlag ist eingegangen und wird geprüft.
                </p>
              ) : (
                <form onSubmit={submit} className="mt-4 space-y-3">
                  <p className="text-label text-muted">
                    Stimmt etwas nicht oder fehlt eine Info? Wähle den Punkt und beschreibe die Änderung — wir prüfen sie.
                  </p>

                  <label className="block text-label font-medium text-ink">
                    Welcher Punkt?
                    <Select value={target} onChange={(e) => setTarget(e.target.value)} className="mt-1">
                      {EDIT_TARGETS.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label}
                        </option>
                      ))}
                    </Select>
                  </label>

                  <label className="block text-label font-medium text-ink">
                    Deine Änderung
                    <Textarea
                      required
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      placeholder="Was sollte geändert oder ergänzt werden?"
                      rows={4}
                      className="mt-1"
                    />
                  </label>

                  <div className="flex flex-wrap gap-3">
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Name (optional)"
                      className="min-w-[8rem] flex-1"
                    />
                    <Input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="E-Mail für Rückfragen (optional)"
                      className="min-w-[8rem] flex-1"
                    />
                  </div>

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

                  {error && <p role="alert" className="text-label text-danger">{error}</p>}

                  <div className="flex items-center justify-end gap-3 pt-1">
                    <button
                      type="button"
                      onClick={close}
                      className="min-h-11 px-3 text-label font-medium text-ink transition-opacity hover:opacity-70"
                    >
                      Abbrechen
                    </button>
                    <Button type="submit" disabled={busy || !message.trim()}>
                      {busy ? "Senden…" : "Vorschlag senden"}
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
