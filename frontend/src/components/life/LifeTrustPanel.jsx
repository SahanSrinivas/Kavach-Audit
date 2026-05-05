import React from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

function Metric({ label, value, suffix = "", hint }) {
  return (
    <div className="rounded-xl border border-[#E1E5EB] bg-[#F8FAFC] px-3 py-2.5 sm:px-4 sm:py-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] sm:text-xs font-semibold uppercase tracking-wide text-[#64748B]">{label}</p>
        {hint ? (
          <span className="group relative shrink-0">
            <Info className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden="true" />
            <span className="sr-only">{hint}</span>
            <span
              role="tooltip"
              className="pointer-events-none absolute right-0 top-full z-10 mt-1 hidden w-56 rounded-lg border border-[#E1E5EB] bg-white p-2 text-[11px] leading-snug text-[#475569] shadow-md group-hover:block group-focus-within:block"
            >
              {hint}
            </span>
          </span>
        ) : null}
      </div>
      <p className="mt-1 font-heading text-lg sm:text-xl font-bold text-[#0B2545] tabular-nums">
        {value == null ? "—" : `${value}${suffix}`}
      </p>
    </div>
  );
}

/**
 * IRDAI-aligned multi-metric panel (definitions surfaced in UI).
 */
export default function LifeTrustPanel({
  selectedId,
  onSelectId,
  rows = [],
  fyLabel = "",
  loading = false,
  error = null,
  selectedFy,
  onSelectFy,
  availableFys = [],
  className,
}) {
  const selected = rows.find((r) => r.id === selectedId) ?? rows[0];
  const showFyPicker = Array.isArray(availableFys) && availableFys.length > 1 && onSelectFy;

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl sm:text-2xl font-bold text-[#0B2545]">Insurer trust panel</h2>
          <p className="mt-1 text-sm text-[#64748B] max-w-2xl leading-relaxed">
            Published metrics from IRDAI reporting are multi-dimensional—there is no single “best” number. Compare
            settlement, speed, persistency, and solvency together.
          </p>
        </div>
        <div className="flex flex-col gap-2 w-full sm:w-auto sm:min-w-[220px]">
          {showFyPicker ? (
            <div>
              <label htmlFor="life-fy-select" className="sr-only">
                Financial year
              </label>
              <select
                id="life-fy-select"
                value={selectedFy ?? ""}
                onChange={(e) => onSelectFy?.(e.target.value)}
                className="w-full h-10 rounded-lg border border-[#E1E5EB] bg-white px-3 text-xs font-semibold text-[#475569] shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8]"
              >
                {availableFys.map((fy) => (
                  <option key={fy} value={fy}>
                    FY {fy.replace("-", "–")}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <div>
            <label htmlFor="life-insurer-select" className="sr-only">
              Select insurer
            </label>
            <select
              id="life-insurer-select"
              value={selected?.id ?? ""}
              onChange={(e) => onSelectId?.(e.target.value)}
              disabled={loading || !!error || rows.length === 0}
              className="w-full h-11 rounded-lg border border-[#E1E5EB] bg-white px-3 text-sm font-medium text-[#0B2545] shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2 disabled:opacity-50"
            >
              {rows.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.shortName}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <p className="text-xs text-[#94A3B8]">{fyLabel || "Loading FY label…"}</p>

      {error ? (
        <p className="text-sm text-[#B22222]" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 animate-pulse">
          {[1, 2, 3, 4, 5].map((k) => (
            <div key={k} className="h-20 rounded-xl bg-[#E1E5EB]/60" />
          ))}
        </div>
      ) : null}

      {!loading && selected ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <Metric
            label="Death claim settlement ratio"
            value={selected.deathClaimSettlementRatio}
            suffix="%"
            hint="Share of death claims settled vs received for the period, as reported in IRDAI disclosures. Not a product recommendation."
          />
          <Metric
            label="Settled within 30 days"
            value={selected.settledWithin30DaysPct}
            suffix="%"
            hint="Individual death claims closed within 30 days where disclosed—speed matters for families."
          />
          <Metric
            label="13th month persistency"
            value={selected.thirteenthMonthPersistencyPct}
            suffix="%"
            hint="Policies still paying premium at the 13th month—signals selling sustainability and customer retention."
          />
          <Metric
            label="25th month persistency"
            value={selected.twentyFifthMonthPersistencyPct}
            suffix="%"
            hint="Longer-horizon retention; useful alongside 13th month figures."
          />
          <Metric
            label="Solvency ratio"
            value={selected.solvencyRatio}
            suffix="×"
            hint="Regulatory solvency margin vs requirement—financial capacity to meet obligations (not claim quality alone)."
          />
        </div>
      ) : null}

      <div className="rounded-xl border border-[#E1E5EB] bg-white p-4 text-xs text-[#64748B] leading-relaxed">
        <p className="font-semibold text-[#0B2545]">Disclaimer</p>
        <p className="mt-1">
          Kavachly shows educational summaries from ingested FY JSON packs (see data/life/). Replace packs with your own
          IRDAI scrape for production accuracy. Do not use this screen alone to buy or switch policies.
        </p>
      </div>
    </div>
  );
}
