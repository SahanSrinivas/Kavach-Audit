/**
 * Life insurer statistics for the Kavachly Trust Panel (MVP).
 *
 * IMPORTANT: These rows are structured for product/COPY review and UI wiring.
 * Production must replace values by ingesting IRDAI Annual Report / Handbook on
 * Indian Insurance Statistics / insurer public disclosures for the labelled FY.
 *
 * Do not treat numbers here as live regulatory filings.
 */
export const LIFE_STATS_FY_LABEL = "FY 2023–24 (illustrative sample for UI)";

/** @typedef {{
 *   id: string;
 *   shortName: string;
 *   legalName: string;
 *   deathClaimSettlementRatio: number | null;
 *   settledWithin30DaysPct: number | null;
 *   thirteenthMonthPersistencyPct: number | null;
 *   twentyFifthMonthPersistencyPct: number | null;
 *   solvencyRatio: number | null;
 * }} LifeInsurerStatRow */

/** @type {LifeInsurerStatRow[]} */
export const LIFE_INSURER_STATS_SAMPLE = [
  {
    id: "lic",
    shortName: "LIC",
    legalName: "Life Insurance Corporation of India",
    deathClaimSettlementRatio: 98.6,
    settledWithin30DaysPct: 97.1,
    thirteenthMonthPersistencyPct: 81.2,
    twentyFifthMonthPersistencyPct: 62.4,
    solvencyRatio: 1.85,
  },
  {
    id: "hdfc-life",
    shortName: "HDFC Life",
    legalName: "HDFC Life Insurance Company Limited",
    deathClaimSettlementRatio: 99.4,
    settledWithin30DaysPct: 99.0,
    thirteenthMonthPersistencyPct: 84.0,
    twentyFifthMonthPersistencyPct: 68.1,
    solvencyRatio: 1.76,
  },
  {
    id: "sbi-life",
    shortName: "SBI Life",
    legalName: "SBI Life Insurance Company Limited",
    deathClaimSettlementRatio: 99.1,
    settledWithin30DaysPct: 98.5,
    thirteenthMonthPersistencyPct: 82.7,
    twentyFifthMonthPersistencyPct: 65.3,
    solvencyRatio: 2.01,
  },
  {
    id: "icici-pru",
    shortName: "ICICI Prudential",
    legalName: "ICICI Prudential Life Insurance Company Limited",
    deathClaimSettlementRatio: 98.7,
    settledWithin30DaysPct: 97.8,
    thirteenthMonthPersistencyPct: 83.5,
    twentyFifthMonthPersistencyPct: 66.0,
    solvencyRatio: 1.94,
  },
  {
    id: "max-life",
    shortName: "Max Life",
    legalName: "Max Life Insurance Company Limited",
    deathClaimSettlementRatio: 99.5,
    settledWithin30DaysPct: 98.9,
    thirteenthMonthPersistencyPct: 85.2,
    twentyFifthMonthPersistencyPct: 69.4,
    solvencyRatio: 1.88,
  },
  {
    id: "bajaj-allianz-life",
    shortName: "Bajaj Allianz Life",
    legalName: "Bajaj Allianz Life Insurance Company Limited",
    deathClaimSettlementRatio: 99.0,
    settledWithin30DaysPct: 97.5,
    thirteenthMonthPersistencyPct: 80.4,
    twentyFifthMonthPersistencyPct: 61.8,
    solvencyRatio: 1.72,
  },
];

export function getLifeInsurerById(id) {
  return LIFE_INSURER_STATS_SAMPLE.find((r) => r.id === id) ?? null;
}
