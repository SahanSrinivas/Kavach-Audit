/**
 * Load IRDAI-style life insurer stat packs from static JSON (ingested per FY).
 * Source files live at public/data/life/ — sync from data/life/ via scripts/ingest_life_stats.py
 */

const PUBLIC_BASE = process.env.PUBLIC_URL || "";

export async function fetchLifeStatsIndex() {
  const res = await fetch(`${PUBLIC_BASE}/data/life/index.json`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Life stats index failed: ${res.status}`);
  return res.json();
}

/**
 * @param {string} fy e.g. "2023-24"
 */
export async function fetchLifeStatsBundle(fy) {
  const res = await fetch(`${PUBLIC_BASE}/data/life/fy-${fy}.json`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Life stats FY ${fy} failed: ${res.status}`);
  return res.json();
}

/**
 * Map API / JSON insurer row to UI row (camelCase consistent with Trust Panel).
 * @param {Record<string, unknown>} raw
 */
export function normalizeInsurerRow(raw) {
  return {
    id: raw.id,
    shortName: raw.shortName,
    legalName: raw.legalName,
    deathClaimSettlementRatio: raw.deathClaimSettlementRatio ?? null,
    settledWithin30DaysPct: raw.settledWithin30DaysPct ?? null,
    thirteenthMonthPersistencyPct: raw.thirteenthMonthPersistencyPct ?? null,
    twentyFifthMonthPersistencyPct: raw.twentyFifthMonthPersistencyPct ?? null,
    solvencyRatio: raw.solvencyRatio ?? null,
    grievancesPerLakhPolicies: raw.grievancesPerLakhPolicies ?? null,
  };
}
