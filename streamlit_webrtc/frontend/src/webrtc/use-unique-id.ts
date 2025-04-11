import { useState, useCallback } from "react";

export function useUniqueId() {
  const [uniqueIds, setUniqueIds] = useState(new Set<string>());
  const getUniqueId = useCallback(() => {
    let id;
    do {
      id = Math.random().toString(36).substring(2, 15);
    } while (uniqueIds.has(id));
    setUniqueIds(new Set(uniqueIds).add(id));
    return id;
  }, [uniqueIds]);
  const resetUniqueIds = useCallback(() => {
    setUniqueIds(new Set<string>());
  }, []);
  return { get: getUniqueId, reset: resetUniqueIds };
}
