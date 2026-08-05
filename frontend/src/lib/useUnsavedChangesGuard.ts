import { useCallback, useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";

export function useUnsavedChangesGuard() {
  const dirtyScopes = useRef(new Set<string>());
  const [, setVersion] = useState(0);

  const markDirty = useCallback((scope = "default") => {
    if (dirtyScopes.current.has(scope)) return;
    dirtyScopes.current.add(scope);
    setVersion((value) => value + 1);
  }, []);

  const markClean = useCallback((scope?: string) => {
    if (scope) dirtyScopes.current.delete(scope);
    else dirtyScopes.current.clear();
    setVersion((value) => value + 1);
  }, []);

  const shouldBlock = useCallback(() => dirtyScopes.current.size > 0, []);
  const blocker = useBlocker(shouldBlock);
  const dirty = dirtyScopes.current.size > 0;

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  return { blocker, dirty, markDirty, markClean };
}
