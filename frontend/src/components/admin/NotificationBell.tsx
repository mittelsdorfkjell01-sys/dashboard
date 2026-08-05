import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
  type AdminNotification,
} from "../../lib/api";
import {
  adminSectionLabel,
  createAdminReturnState,
} from "../../lib/adminNavigation";

const POLL_MS = 60_000; // minute polling for the badge

/**
 * Operator-notification bell for the admin chrome (Sprint 9). Polls the cheap
 * unread-count every minute; opening the panel loads the list and offers
 * mark-read / mark-all-read. Clicking one that links a spot jumps to it.
 */
export default function NotificationBell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AdminNotification[] | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Badge: poll the count on a minute interval (and once on mount).
  useEffect(() => {
    let alive = true;
    const tick = () =>
      getUnreadNotificationCount()
        .then((r) => alive && setUnread(r.count))
        .catch(() => {});
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      getNotifications()
        .then((r) => {
          setItems(r.items);
          setUnread(r.unread);
        })
        .catch(() => setItems([]));
    }
  };

  const onItem = async (n: AdminNotification) => {
    if (!n.read) {
      await markNotificationRead(n.id).catch(() => {});
      setItems((prev) => prev?.map((x) => (x.id === n.id ? { ...x, read: true } : x)) ?? null);
      setUnread((u) => Math.max(0, u - 1));
    }
    setOpen(false);
    if (n.spot_id) {
      navigate(`/admin/spot/${n.spot_id}/edit`, {
        state: createAdminReturnState(location, adminSectionLabel(location.pathname)),
      });
    } else {
      navigate("/admin/review");
    }
  };

  const markAll = async () => {
    await markAllNotificationsRead().catch(() => {});
    setItems((prev) => prev?.map((x) => ({ ...x, read: true })) ?? null);
    setUnread(0);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-label={`Benachrichtigungen${unread ? `, ${unread} ungelesen` : ""}`}
        className="relative grid h-8 w-8 place-items-center rounded-md border border-admin-border bg-admin-surface text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 grid min-w-[16px] place-items-center rounded-full bg-admin-primary px-1 text-[10px] font-semibold leading-[16px] text-admin-primary-fg">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-lg border border-admin-border bg-admin-elevated"
          style={{ boxShadow: "var(--a-shadow-pop)" }}
        >
          <div className="flex items-center justify-between border-b border-admin-border px-3 py-2">
            <span className="text-label font-semibold text-admin-fg">Benachrichtigungen</span>
            {(items?.some((i) => !i.read) ?? false) && (
              <button
                type="button"
                onClick={markAll}
                className="text-caption font-medium text-admin-primary hover:underline"
              >
                Alle gelesen
              </button>
            )}
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {items === null ? (
              <p className="px-3 py-6 text-center text-caption text-admin-muted">Lädt…</p>
            ) : items.length === 0 ? (
              <p className="px-3 py-6 text-center text-caption text-admin-muted">
                Keine Benachrichtigungen.
              </p>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => onItem(n)}
                  className={`block w-full border-b border-admin-border-subtle px-3 py-2 text-left transition-colors last:border-0 hover:bg-admin-hover ${
                    n.read ? "" : "bg-admin-primary-bg"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-admin-primary" />}
                    <div className="min-w-0">
                      <p className="text-label text-admin-fg">{n.message}</p>
                      <p className="admin-mono mt-0.5 text-caption text-admin-muted">
                        {new Date(n.created_at).toLocaleString("de-DE")}
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
