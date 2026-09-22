import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as account from "../lib/account";
import type { Account } from "../lib/account";

interface AuthValue {
  /** Signed-in account, or null when logged out. */
  user: Account | null;
  /** False until the initial session lookup has run (avoids UI flicker). */
  ready: boolean;
  sessionError: string | null;
  refreshSession: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Replace the cached account after a profile edit. */
  setUser: (u: Account | null) => void;
}

const AuthCtx = createContext<AuthValue | null>(null);

/**
 * Holds the public-account session, resolved from the real /account endpoints
 * (see lib/account). `ready` guards the initial session lookup so the UI does
 * not flicker between logged-out and logged-in on first paint.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const refreshSession = async () => {
    setSessionError(null);
    try {
      setUser(await account.fetchSession());
    } catch {
      setSessionError("Dein Kontostatus konnte nicht geladen werden. Prüfe die Verbindung und versuche es erneut.");
    } finally {
      setReady(true);
    }
  };

  useEffect(() => {
    void refreshSession();
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      sessionError,
      refreshSession,
      async login(email, password) {
        setUser(await account.login({ email, password }));
        setSessionError(null);
      },
      async register(email, displayName) {
        await account.register({ email, displayName });
      },
      async logout() {
        await account.logout();
        setUser(null);
      },
      setUser,
    }),
    [user, ready, sessionError]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("useAuth must be used within <AuthProvider>.");
  return v;
}
