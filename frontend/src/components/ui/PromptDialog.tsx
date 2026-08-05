import { useEffect, useRef, useState } from "react";
import Modal from "./Modal";
import Button from "./Button";
import Input from "./Input";
import ConfirmDialog from "./ConfirmDialog";

/**
 * Reusable single-input dialog — the accessible replacement for
 * `window.prompt`. Confirms on Enter, cancels on Esc; the field is focused and
 * cleared each time it opens. Supports `type="password"` for secret entry.
 */
export default function PromptDialog({
  open,
  title,
  label,
  confirmText = "Speichern",
  type = "text",
  initialValue = "",
  placeholder,
  busy = false,
  allowEmpty = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  label?: string;
  confirmText?: string;
  type?: "text" | "password";
  initialValue?: string;
  placeholder?: string;
  busy?: boolean;
  /** Allow confirming with an empty field (e.g. an optional note). */
  allowEmpty?: boolean;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initialValue);
  const [discardOpen, setDiscardOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setValue(initialValue);
      setDiscardOpen(false);
      // Focus after the modal has mounted.
      queueMicrotask(() => inputRef.current?.focus());
    }
  }, [open, initialValue]);

  const submit = () => {
    if (busy || (!allowEmpty && !value.trim())) return;
    onConfirm(value);
  };

  const requestCancel = () => {
    if (busy) return;
    if (value !== initialValue) setDiscardOpen(true);
    else onCancel();
  };

  return (
    <>
    <Modal open={open} onClose={requestCancel} labelledBy="prompt-title">
      <h2 id="prompt-title" className="text-ui font-semibold text-ink">
        {title}
      </h2>
      {label && <label htmlFor="prompt-input" className="mt-3 block text-label text-ink-soft">{label}</label>}
      <Input
        id="prompt-input"
        ref={inputRef}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={type === "password" ? "new-password" : "off"}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            submit();
          }
        }}
        className="mt-2"
      />
      <div className="mt-5 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={requestCancel} disabled={busy}>
          Abbrechen
        </Button>
        <Button onClick={submit} disabled={busy || (!allowEmpty && !value.trim())}>
          {busy ? "…" : confirmText}
        </Button>
      </div>
    </Modal>
    <ConfirmDialog
      open={discardOpen}
      title="Eingabe verwerfen?"
      message="Die noch nicht gespeicherte Eingabe geht verloren."
      confirmText="Verwerfen"
      variant="danger"
      onCancel={() => setDiscardOpen(false)}
      onConfirm={() => {
        setDiscardOpen(false);
        onCancel();
      }}
    />
    </>
  );
}
