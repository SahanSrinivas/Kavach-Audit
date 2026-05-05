/**
 * @deprecated Direct imports — use fetchLifeStatsBundle from @/lib/lifeStats.
 * Kept for backward-compatible helpers only.
 */
export { fetchLifeStatsIndex, fetchLifeStatsBundle, normalizeInsurerRow } from "@/lib/lifeStats";

export function getLifeInsurerById(rows, id) {
  if (!Array.isArray(rows)) return null;
  return rows.find((r) => r.id === id) ?? null;
}
