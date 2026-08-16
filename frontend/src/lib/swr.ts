// A tiny stale-while-revalidate data cache — no external dependency. Caches
// fetch results by key in a module-level store shared across the app, so the
// same key resolves to one in-flight request and one cached value. Revisiting a
// page renders cached data instantly and refreshes in the background, instead of
// flashing a skeleton and re-fetching from scratch every time.

import { useEffect, useReducer } from "react";
import { ApiError } from "./api";

const errMessage = (e: unknown) =>
  e instanceof ApiError ? e.message : "Unerwarteter Fehler.";

interface Entry<T> {
  data?: T;
  error?: string;
  inflight?: Promise<void>;
  ts?: number;
}

const store = new Map<string, Entry<unknown>>();
const subscribers = new Map<string, Set<() => void>>();
const MAX_ENTRIES = 200;
const MAX_AGE_MS = 5 * 60 * 1000;
const versions = new Map<string, number>();

function storeEntry(key: string, entry: Entry<unknown>) {
  store.delete(key);
  store.set(key, entry);
  while (store.size > MAX_ENTRIES) {
    const oldest = store.keys().next().value as string | undefined;
    if (!oldest) break;
    store.delete(oldest);
    subscribers.delete(oldest);
  }
}

function notify(key: string) {
  subscribers.get(key)?.forEach((fn) => fn());
}

/** Fire (or join) a fetch for `key`, update the cache, then notify subscribers. */
export function revalidate<T>(
  key: string,
  fetcher: () => Promise<T>
): Promise<void> {
  const existing = store.get(key) as Entry<T> | undefined;
  if (existing?.inflight) return existing.inflight;
  const version = versions.get(key) ?? 0;

  const inflight = fetcher()
    .then((data) => {
      // A local mutation made while this request was in flight is newer than
      // its response. Never let that stale response erase the new item.
      if ((versions.get(key) ?? 0) === version) {
        storeEntry(key, { data, ts: Date.now() });
      }
    })
    .catch((err) => {
      const cur = store.get(key) as Entry<T> | undefined;
      // Keep stale data on a background failure; only surface an error when
      // there is nothing cached to show.
      if (cur && cur.data !== undefined) {
        storeEntry(key, { data: cur.data, ts: cur.ts });
      } else {
        storeEntry(key, { error: errMessage(err), ts: Date.now() });
      }
    })
    .finally(() => notify(key));

  storeEntry(key, { ...(existing ?? {}), inflight });
  return inflight;
}

/** Read a cache entry (test/debug helper). */
export function peek<T>(key: string): Entry<T> | undefined {
  return store.get(key) as Entry<T> | undefined;
}

/** Clear the whole cache — used by tests. */
export function __resetCache() {
  store.clear();
  subscribers.clear();
  versions.clear();
}

/** Update cached data immediately and detach any older in-flight response. */
export function mutate<T>(key: string, update: (current: T | undefined) => T) {
  const existing = store.get(key) as Entry<T> | undefined;
  versions.set(key, (versions.get(key) ?? 0) + 1);
  storeEntry(key, { data: update(existing?.data), ts: Date.now() });
  notify(key);
}

export interface SwrState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

interface PersistentEnvelope<T> {
  version: 1;
  savedAt: number;
  data: T;
}

export interface PersistentSwrOptions {
  storageKey: string;
  maxAgeMs: number;
}

function browserStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

/** Seed the memory cache synchronously from a bounded, versioned public-data
 * snapshot. This makes a returning visitor's first paint independent of a
 * serverless/DB cold start; the normal SWR request still refreshes it. */
export function hydratePersistent<T>(
  key: string,
  options: PersistentSwrOptions,
  storage: Pick<Storage, "getItem" | "removeItem"> | null = browserStorage(),
  now = Date.now(),
): boolean {
  if (store.has(key) || !storage) return false;
  try {
    const raw = storage.getItem(options.storageKey);
    if (!raw) return false;
    const saved = JSON.parse(raw) as PersistentEnvelope<T>;
    if (
      saved?.version !== 1 ||
      !Number.isFinite(saved.savedAt) ||
      now - saved.savedAt > options.maxAgeMs ||
      saved.data == null
    ) {
      storage.removeItem(options.storageKey);
      return false;
    }
    // Treat the restored value as fresh in memory. Its original age is still
    // enforced above, and useSwr starts a background revalidation immediately.
    storeEntry(key, { data: saved.data, ts: now });
    return true;
  } catch {
    try { storage.removeItem(options.storageKey); } catch { /* unavailable */ }
    return false;
  }
}

function persistPublicData<T>(options: PersistentSwrOptions, data: T) {
  try {
    browserStorage()?.setItem(
      options.storageKey,
      JSON.stringify({ version: 1, savedAt: Date.now(), data } satisfies PersistentEnvelope<T>),
    );
  } catch {
    // Private mode/quota: the in-memory SWR cache remains fully functional.
  }
}

/**
 * Stale-while-revalidate data hook. A `null` key disables the fetch (for
 * dependent/conditional queries). The `key` fully identifies the request, so
 * `fetcher` is deliberately not a dependency.
 */
export function useSwr<T>(
  key: string | null,
  fetcher: () => Promise<T>
): SwrState<T> {
  const [, force] = useReducer((n: number) => n + 1, 0);

  useEffect(() => {
    if (!key) return;
    let set = subscribers.get(key);
    if (!set) {
      set = new Set();
      subscribers.set(key, set);
    }
    set.add(force);
    void revalidate(key, fetcher);
    return () => {
      set!.delete(force);
      if (set!.size === 0) subscribers.delete(key);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const entry = key ? (store.get(key) as Entry<T> | undefined) : undefined;
  const expired = !!entry?.ts && Date.now() - entry.ts > MAX_AGE_MS;
  const hasData = !!entry && entry.data !== undefined;
  return {
    data: hasData && !expired ? (entry!.data as T) : null,
    loading: !!key && (!hasData || expired) && !entry?.error,
    error: entry?.error ?? null,
    reload: () => {
      if (key) void revalidate(key, fetcher);
    },
  };
}

/** SWR for non-sensitive public catalogue data that should survive reloads. */
export function usePersistentSwr<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  options: PersistentSwrOptions | null,
): SwrState<T> {
  if (key && options) hydratePersistent<T>(key, options);
  return useSwr(key, async () => {
    const data = await fetcher();
    if (options) persistPublicData(options, data);
    return data;
  });
}
