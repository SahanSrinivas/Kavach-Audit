import React from "react";
import { FileText } from "lucide-react";
import { formatINR } from "../../lib/currency";

// Single policy row in the dashboard list.
// Flag count proxy from sub_limits length is brittle — replaced in commit 4
// with related_policy_id-filtered findings.
export default function PolicyCard({ policy }) {
  const flagCount = policy.parsed_fields?.sub_limits?.length || 0;
  const flagState = flagCount === 0 ? "ok" : flagCount <= 2 ? "warn" : "critical";
  const badge =
    flagState === "ok"
      ? { label: "✓ no issues", cls: "text-[#0F7B4F] bg-[#0F7B4F]/10" }
      : flagState === "warn"
        ? { label: `⚠ ${flagCount} red flags`, cls: "text-[#D97706] bg-[#D97706]/10" }
        : { label: `🚩 ${flagCount} critical`, cls: "text-[#B22222] bg-[#B22222]/10" };
  return (
    <article
      data-testid={`policy-card-${policy.id}`}
      className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card flex items-start gap-4"
    >
      <span className="w-12 h-12 rounded-lg bg-[#13A8A8]/10 flex items-center justify-center flex-none">
        <FileText className="w-5 h-5 text-[#13A8A8]" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold text-[#0B2545] truncate">{policy.insurer}</p>
            <p className="text-sm text-[#475569]">
              {policy.policy_name || policy.type} · cover {formatINR(policy.sum_insured, { short: true })}
            </p>
          </div>
          <span className={`text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md whitespace-nowrap ${badge.cls}`}>
            {badge.label}
          </span>
        </div>
        <p className="mt-1.5 text-xs text-[#475569]">
          Premium {formatINR(policy.premium)} / yr
          {policy.end_date && (
            <>
              {" · "}Renews{" "}
              {new Date(policy.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
            </>
          )}
        </p>
      </div>
    </article>
  );
}
