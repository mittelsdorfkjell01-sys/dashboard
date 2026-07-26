import { useState, type FormEvent } from "react";
import { ApiError, postTip } from "../lib/api";
import { Button, Input, Textarea } from "./ui";

/**
 * Text-only comment composer for the Kommentare overlay. Posts through the
 * existing `tips` endpoint (`POST /spots/:id/tips`) — a spot "Tipp" is exactly
 * a free-text community comment, no star rating attached. Anonymous-friendly
 * (name optional, like the tip flow); a hidden honeypot field mirrors the
 * other public forms' spam guard.
 */
export default function CommentComposer({
  spotId,
  onPosted,
  onCancel,
}: {
  spotId: string;
  onPosted: () => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const [author, setAuthor] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (website) return; // honeypot tripped — silently drop
    if (!text.trim()) return setError("Bitte einen Kommentar schreiben.");
    setBusy(true);
    setError(null);
    try {
      await postTip(spotId, {
        body: text.trim(),
        author_name: author.trim() || undefined,
        website,
      });
      setText("");
      setAuthor("");
      setNotice("Danke! Dein Kommentar ist online.");
      setTimeout(() => {
        setNotice(null);
        onPosted();
      }, 1200);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Senden fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="rounded-3xl border border-line bg-white p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <p className="text-body font-medium text-ink">Kommentar schreiben</p>
        <button type="button" onClick={onCancel} className="text-label text-muted hover:text-teal">
          Schließen
        </button>
      </div>

      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Wie war's? Dein Tipp oder Kommentar zum Spot…"
        rows={4}
        className="mt-3"
      />
      <Input
        value={author}
        onChange={(e) => setAuthor(e.target.value)}
        placeholder="Dein Name (optional)"
        className="mt-2"
      />

      {/* Honeypot — hidden from users, catches naive bots. */}
      <input
        type="text"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        className="hidden"
      />

      {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}
      {notice && <p role="status" className="mt-2 text-label text-green">{notice}</p>}

      <Button type="submit" disabled={busy || !text.trim()} className="mt-3">
        {busy ? "Senden…" : "Kommentar posten"}
      </Button>
    </form>
  );
}
