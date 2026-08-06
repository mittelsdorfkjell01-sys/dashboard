import { useCallback, useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";

function normalizeFormValue(value: unknown): unknown {
  if (value instanceof File) {
    return { name: value.name, size: value.size, type: value.type, lastModified: value.lastModified };
  }
  if (Array.isArray(value)) return value.map(normalizeFormValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entry]) => [key, normalizeFormValue(entry)])
    );
  }
  return value;
}

export const stableFormValue = (value: unknown) =>
  JSON.stringify(normalizeFormValue(value));

export const areFormValuesEqual = (left: unknown, right: unknown) =>
  stableFormValue(left) === stableFormValue(right);

export function useFormDirty(current: unknown, initial: unknown, active = true) {
  return active && !areFormValuesEqual(current, initial);
}

export function useUnsavedChangesGuard() {
  const dirtyScopes = useRef(new Set<string>());
  const [, setVersion] = useState(0);

  const markDirty = useCallback((scope = "default") => {
    if (dirtyScopes.current.has(scope)) return;
    dirtyScopes.current.add(scope);
    setVersion((value) => value + 1);
  }, []);

  const markClean = useCallback((scope?: string) => {
    const changed = scope
      ? dirtyScopes.current.delete(scope)
      : dirtyScopes.current.size > 0;
    if (!scope) dirtyScopes.current.clear();
    if (!changed) return;
    setVersion((value) => value + 1);
  }, []);

  const setDirty = useCallback((scope: string, value: boolean) => {
    const hasScope = dirtyScopes.current.has(scope);
    if (value === hasScope) return;
    if (value) dirtyScopes.current.add(scope);
    else dirtyScopes.current.delete(scope);
    setVersion((version) => version + 1);
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

  return { blocker, dirty, markDirty, markClean, setDirty };
}
