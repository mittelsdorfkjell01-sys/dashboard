import { useCallback, useEffect, useState } from "react";
import { ApiError, getSpotTips, hideTip, restoreTip, type ReviewTip } from "../../lib/api";
import { groupTipThreads } from "../../lib/tipThreads";
import Button from "../ui/Button";

/**
 * Per-spot comment moderation (Sprint 2). Lists every comment on the spot —
 * published and hidden — grouped into threads, so a reply is shown under its
 * parent for context. Any comment can be hidden or restored (not just flagged
 * ones); hidden comments stay listed so they can be brought back.
 */
export default function SpotCommentsPanel({ spotId }: { spotId: string }) {
  const [tips, setTips] = useState<ReviewTip[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    getSpotTips(spotId)
      .then((r) => setTips(r.items))
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Kommentare laden fehlgeschlagen.")
      );
  }, [spotId]);

  useEffect(load, [load]);

  const act = async (id: string, fn: (id: string) => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn(id);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusyId(null);
    }
  };

  if (error && !tips) return <p className="text-label text-admin-danger">{error}</p>;
  if (!tips) return <p className="text-label text-muted">Kommentare werden geladen…</p>;
  if (tips.length === 0)
    return <p className="text-label text-muted">Noch keine Kommentare.</p>;

  const threads = groupTipThreads(tips);

  return (
    <div className="space-y-3">
      {error && <p className="text-label text-admin-danger">{error}</p>}
      {threads.map(({ root, replies }) => (
        <div key={root.id} className="rounded-lg border border-line bg-white p-3">
          <Comment tip={root} busy={busyId === root.id} onAct={act} />
          {replies.length > 0 && (
            <div className="mt-3 space-y-3 border-l border-line pl-3">
              {replies.map((r) => (
                <div key={r.id}>
                  <p className="text-caption text-muted">Antwort an {root.author_name}</p>
                  <Comment tip={r} busy={busyId === r.id} onAct={act} />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Comment({
  tip,
  busy,
  onAct,
}: {
  tip: ReviewTip;
  busy: boolean;
  onAct: (id: string, fn: (id: string) => Promise<unknown>) => void;
}) {
  const hidden = tip.status === "hidden";
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-caption text-muted">
          <span className="font-medium text-ink-soft">{tip.author_name}</span>
          {tip.flagged && (
            <span className="rounded bg-orange/15 px-1.5 py-0.5 font-semibold text-ink">
              gemeldet
            </span>
          )}
          {hidden && (
            <span className="rounded bg-line px-1.5 py-0.5 font-semibold text-muted">
              verborgen
            </span>
          )}
        </div>
        <p className={`text-label ${hidden ? "text-muted line-through" : "text-ink"}`}>
          {tip.body}
        </p>
      </div>
      {hidden ? (
        <Button
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => onAct(tip.id, restoreTip)}
        >
          Wiederherstellen
        </Button>
      ) : (
        <Button
          size="sm"
          variant="danger"
          disabled={busy}
          onClick={() => onAct(tip.id, hideTip)}
        >
          Verbergen
        </Button>
      )}
    </div>
  );
}
