import { useRef, useCallback } from "react";

export function useUniqueId() {
  const uniqueIds = useRef(new Set<string>());
  const getUniqueId = useCallback(() => {
    let id;
    do {
      id = Math.random().toString(36).substring(2, 15);
    } while (uniqueIds.current.has(id));
    uniqueIds.current.add(id);
    return id;
  }, [uniqueIds]);
  const resetUniqueIds = useCallback(() => {
    uniqueIds.current = new Set<string>();
  }, []);
  return { get: getUniqueId, reset: resetUniqueIds };
}
