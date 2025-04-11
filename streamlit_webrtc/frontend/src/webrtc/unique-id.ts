const uniqueIds = new Set<string>();
export function getUniqueId(): string {
  let id;
  do {
    id = Math.random().toString(36).substring(2, 15);
  } while (uniqueIds.has(id));
  uniqueIds.add(id);
  return id;
}
