/** Secrets that let an anonymous author withdraw their own comment.
 *
 * The server hands one out exactly once, when the comment is created, and
 * stores only its hash. This keeps it on the device that wrote the comment, so
 * the author can take it back without ever making an account.
 *
 * `localStorage`, not `sessionStorage`: the point is to still be able to delete
 * the comment tomorrow. Losing it (cleared browser, other device) means the
 * comment stays and the operator has to remove it — which is the same position
 * anonymous authors were in before, so the failure mode is the old behaviour
 * rather than a new one.
 *
 * Every access is wrapped: private windows and blocked site data throw on
 * `localStorage`, and a comment box must not fall over because of it.
 */

const KEY = "swd:withdraw-tokens";

type Store = Record<string, string>;

function read(): Store {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function write(store: Store) {
  try {
    localStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    /* no storage — the comment simply cannot be withdrawn from here */
  }
}

export function rememberWithdrawToken(tipId: string, token: string) {
  const store = read();
  store[tipId] = token;
  write(store);
}

export function withdrawToken(tipId: string): string | null {
  return read()[tipId] ?? null;
}

export function forgetWithdrawToken(tipId: string) {
  const store = read();
  if (!(tipId in store)) return;
  delete store[tipId];
  write(store);
}
