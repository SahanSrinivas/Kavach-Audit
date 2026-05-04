import React from "react";
import { FileText } from "lucide-react";
import { formatINR } from "../../lib/currency";

// Single policy row in the dashboard list.
//
// Title rule: if the user gave the policy a nickname ("Father's policy"),
// that's the primary line and insurer is demoted to the sub-line — that's
// the whole point of the v0.5.2 nickname feature. Legacy policies (no
// nickname, including all rows uploaded before that release) keep the
// previous behavior with insurer as the title.
//
// Chip rule: counts the audit findings whose related_policy_id === this
// policy. Severity drives color (any "red" → critical/red; else "amber"
// → warn/amber; none → ok/green). Info-level findings are educational
// notes, not issues, so they don't count.
//
// Tap behavior: when onSelect is provided, the whole card becomes a
// button that calls onSelect(policy.id) — that's what enters the
// per-policy detail view. Falls back to a non-interactive article when
// onSelect is omitted (preserves the v0.5.x behavior for any caller
// that wants a static card).
export default function PolicyCard({ policy, findingsForPolicy = [], onSelect }) {
  const hasNickname = Boolean(policy.policy_nickname);
  const primaryTitle = hasNickname ? policy.policy_nickname : policy.insurer;
  const productLabel = policy.policy_name || policy.type;

  const issues = findingsForPolicy.filter((f) => f.severity !== "info");
  const count = issues.length;
  const hasRed = issues.some((f) => f.severity === "red");

  let badge;
  if (count === 0) {
    badge = { label: "✓ no issues", cls: "text-[#0F7B4F] bg-[#0F7B4F]/10" };
  } else if (hasRed) {
    badge = {
      label: `🚩 ${count} critical`,
      cls: "text-[#B22222] bg-[#B22222]/10",
    };
  } else {
    badge = {
      label: `⚠ ${count} red flag${count === 1 ? "" : "s"}`,
      cls: "text-[#D97706] bg-[#D97706]/10",
    };
  }
  const Wrapper = onSelect ? "button" : "article";
  const wrapperProps = onSelect
    ? { type: "button", onClick: () => onSelect(policy.id) }
    : {};

  return (
    <Wrapper
      data-testid={`policy-card-${policy.id}`}
      {...wrapperProps}
      className={`w-full text-left p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card flex items-start gap-4 ${
        onSelect ? "hover:border-[#13A8A8]/40 transition-colors" : ""
      }`}
    >
      <span className="w-12 h-12 rounded-lg bg-[#13A8A8]/10 flex items-center justify-center flex-none">
        <FileText className="w-5 h-5 text-[#13A8A8]" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p
              data-testid="policy-card-title"
              className="font-semibold text-[#0B2545] truncate"
            >
              {primaryTitle}
            </p>
            <p className="text-sm text-[#475569] truncate">
              {hasNickname && <>{policy.insurer} · </>}
              {productLabel} · cover {formatINR(policy.sum_insured, { short: true })}
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
    </Wrapper>
  );
}
