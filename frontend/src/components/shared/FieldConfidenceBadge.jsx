import React from "react";
import { AlertCircle, CheckCircle2, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Tier badge shared by life extract (numeric score) and health parser (often score=null).
 * Life: tier may be high / medium / low with a number.
 * Health (path A): tier is high | low only, score omitted — badge still matches visually.
 */
export default function FieldConfidenceBadge({ tier, score, verifyInPdf }) {
  const label =
    tier === "high" ? "High confidence" : tier === "medium" ? "Check PDF" : "Verify in PDF";

  const showNumeric = typeof score === "number" && !Number.isNaN(score);

  return (
    <div className="flex flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-2 shrink-0">
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
          tier === "high" && "bg-[#0F7B4F]/12 text-[#0F7B4F]",
          tier === "medium" && "bg-amber-100 text-amber-800",
          tier === "low" && "bg-[#B22222]/10 text-[#B22222]",
        )}
      >
        {tier === "high" ? (
          <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
        ) : verifyInPdf ? (
          <HelpCircle className="w-3 h-3" aria-hidden="true" />
        ) : (
          <AlertCircle className="w-3 h-3" aria-hidden="true" />
        )}
        {label}
      </span>
      {showNumeric ? (
        <span className="text-[10px] text-[#94A3B8] tabular-nums">{score.toFixed(2)}</span>
      ) : null}
    </div>
  );
}
