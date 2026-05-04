import React from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../ui/sheet";

// Per-score "show your work" panel. Reads breakdown.details — a
// heterogeneous dict (numbers, strings, arrays, ranges) — and renders
// it as plain key/value rows.
//
// Rich, content-designed rendering of breakdowns.details is deferred
// to v1.1 (see docs/DASHBOARD_IA.md §1.4 gap #7). For now we just don't
// crash on any value type and surface what the engine sent.

const SCORE_LABEL = {
  coverage: "Coverage",
  cost: "Cost",
  claim_readiness: "Claim readiness",
  gap: "Gap",
};

const SCORE_BLURB = {
  coverage: "How much of your ideal cover you currently hold.",
  cost: "How your premiums compare to the market for similar policies.",
  claim_readiness: "How likely a claim will pay out cleanly when you file one.",
  gap: "Categories of insurance you're missing or underinsured in.",
};

function humanizeKey(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(val) {
  if (val === null || val === undefined) return "—";
  if (typeof val === "number") return val.toLocaleString("en-IN");
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "string") return val;
  if (Array.isArray(val)) {
    // Heuristic: 2-element number array is a range like [p25, p75].
    if (val.length === 2 && val.every((x) => typeof x === "number")) {
      return `${val[0].toLocaleString("en-IN")} – ${val[1].toLocaleString("en-IN")}`;
    }
    return val.map(humanizeKey).join(", ");
  }
  return JSON.stringify(val);
}

export default function ScoreBreakdownDrawer({ open, onOpenChange, scoreKey, breakdown }) {
  const label = scoreKey ? SCORE_LABEL[scoreKey] : "";
  const blurb = scoreKey ? SCORE_BLURB[scoreKey] : "";
  const value = breakdown?.value;
  const details = breakdown?.details || {};

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="rounded-t-2xl max-h-[85dvh] overflow-y-auto"
        data-testid={`score-drawer-${scoreKey || "none"}`}
      >
        <SheetHeader>
          <SheetTitle className="font-heading text-2xl text-[#0B2545]">
            {label}
            {value !== undefined && value !== null && (
              <span className="ml-3 text-[#13A8A8] font-bold">{value}/100</span>
            )}
          </SheetTitle>
          <SheetDescription className="text-[#475569]">{blurb}</SheetDescription>
        </SheetHeader>

        <div className="mt-6">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
            How we got there
          </p>
          {Object.keys(details).length === 0 ? (
            <p className="text-sm text-[#475569]">
              No breakdown details for this score yet.
            </p>
          ) : (
            <dl className="space-y-2.5">
              {Object.entries(details).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 border-b border-[#E1E5EB] pb-2">
                  <dt className="text-sm text-[#475569]">{humanizeKey(k)}</dt>
                  <dd className="text-sm font-semibold text-[#0B2545] text-right">
                    {formatValue(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
