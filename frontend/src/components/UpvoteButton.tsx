import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError, setCommentUpvote } from "../lib/api";

export default function UpvoteButton({ kind, id, count, active }: { kind: "rating" | "tip"; id: string; count: number; active: boolean }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [value, setValue] = useState(count);
  const [pressed, setPressed] = useState(active);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // A short pop on the arrow when the vote lands. The count already changes
  // instantly; this is the part that makes the tap feel answered rather than
  // merely recorded. Cleared on a timer so a second tap can play it again.
  const [popping, setPopping] = useState(false);

  const toggle = async () => {
    if (!user) {
      navigate(`/anmelden?mode=login&redirect=${encodeURIComponent(location.pathname + location.search)}`);
      return;
    }
    if (busy) return;
    const next = !pressed;
    const before = { value, pressed };
    setPressed(next);
    setValue(Math.max(0, value + (next ? 1 : -1)));
    if (next) {
      setPopping(true);
      window.setTimeout(() => setPopping(false), 220);
    }
    setBusy(true);
    setError("");
    try {
      const result = await setCommentUpvote(kind, id, next);
      setValue(result.count);
      setPressed(result.viewer_upvoted);
    } catch (err) {
      setValue(before.value);
      setPressed(before.pressed);
      setError(err instanceof ApiError ? err.message : "Upvote fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return <span className="inline-flex items-center gap-1.5">
    <button type="button" aria-pressed={pressed} disabled={busy} onClick={toggle} className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-card px-2 text-caption font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${pressed ? "text-accent" : "text-muted hover:text-ink"}`}>
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 20 20" fill="none" className={`transition-transform duration-base motion-reduce:transition-none ${popping ? "-translate-y-0.5 scale-125" : ""}`}><path d="m5 9 5-5 5 5M10 4v12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      {/* No "0". A row of zeroes reads as an empty form; the arrow alone
          is an invitation, and the number appears once there is one. */}
      {value > 0 && <span>{value}</span>}
      <span className="sr-only">{value === 1 ? "1 Upvote" : `${value} Upvotes`}</span>
    </button>
    {error && <span role="alert" className="sr-only">{error}</span>}
  </span>;
}
