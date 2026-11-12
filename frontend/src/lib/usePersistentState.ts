import { useEffect, useState } from "react";

// Bump the version when the persisted shapes change, so stale drafts are ignored.
const PREFIX = "protolab:v1:";

/** useState backed by localStorage so drafts survive a page reload. */
export function usePersistentState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(PREFIX + key);
      return stored === null ? initial : (JSON.parse(stored) as T);
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch {
      // Quota exceeded or storage blocked: keep working in memory only.
    }
  }, [key, value]);

  return [value, setValue] as const;
}

export function clearPersistedState(): void {
  try {
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith(PREFIX))
      .forEach((key) => window.localStorage.removeItem(key));
  } catch {
    // Storage unavailable: nothing to clear.
  }
}
