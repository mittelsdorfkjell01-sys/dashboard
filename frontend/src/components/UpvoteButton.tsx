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
    <button type="button" aria-pressed={pressed} disabled={busy} onClick={toggle} className={`inline-flex min-h-10 items-center gap-1.5 rounded-xl px-2 text-caption font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ${pressed ? "text-teal" : "text-muted hover:text-ink"}`}>
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="m5 9 5-5 5 5M10 4v12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <span>{value}</span><span className="sr-only">Upvotes</span>
    </button>
    {error && <span role="alert" className="sr-only">{error}</span>}
  </span>;
}
