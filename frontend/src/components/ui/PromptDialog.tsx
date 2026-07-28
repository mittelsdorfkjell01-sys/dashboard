import { useEffect, useRef, useState } from "react";
import Modal from "./Modal";
import Button from "./Button";
import Input from "./Input";

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
  onConfirm: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setValue(initialValue);
      // Focus after the modal has mounted.
      queueMicrotask(() => inputRef.current?.focus());
    }
  }, [open, initialValue]);

  const submit = () => {
    if (!value.trim() || busy) return;
    onConfirm(value);
  };

  return (
    <Modal open={open} onClose={onCancel} labelledBy="prompt-title">
      <h2 id="prompt-title" className="text-ui font-semibold text-ink">
        {title}
      </h2>
      {label && <label className="mt-3 block text-label text-ink-soft">{label}</label>}
      <Input
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
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          Abbrechen
        </Button>
        <Button onClick={submit} disabled={busy || !value.trim()}>
          {busy ? "…" : confirmText}
        </Button>
      </div>
    </Modal>
  );
}
