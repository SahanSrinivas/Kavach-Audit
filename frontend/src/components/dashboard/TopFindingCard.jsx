import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldOff, Clock, ShieldCheck } from "lucide-react";

// Hero treatment for the single most important finding. Used on the
// portfolio view (audit.findings[0]) and the policy detail view
// (filtered to that policy). When there's no finding to show, renders
// a friendly empty state instead of disappearing.
//
// The full collapsible FindingCard already exists at
// components/FindingCard.jsx — Stage6Audit uses it. This is the
// dashboard-only hero variant: always expanded, single CTA.

const ICONS = {
  "alert-triangle": AlertTriangle,
  "shield-off": ShieldOff,
  clock: Clock,
};

const SEVERITY_STYLE = {
  red: {
    border: "border-[#B22222]/30",
    bg: "bg-[#B22222]/5",
    icon: "text-[#B22222] bg-[#B22222]/10",
    flag: "🚩",
  },
  amber: {
    border: "border-[#D97706]/30",
    bg: "bg-[#D97706]/5",
    icon: "text-[#D97706] bg-[#D97706]/10",
    flag: "⚠️",
  },
  info: {
    border: "border-[#13A8A8]/30",
    bg: "bg-[#13A8A8]/5",
    icon: "text-[#13A8A8] bg-[#13A8A8]/10",
    flag: "ℹ️",
  },
};

export default function TopFindingCard({
  finding,
  onFix,
  emptyMessage = "No red flags found in your current cover.",
}) {
  if (!finding) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        data-testid="top-finding-empty"
        className="p-5 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card flex items-center gap-4"
      >
        <span className="w-10 h-10 rounded-lg bg-[#0F7B4F]/10 text-[#0F7B4F] flex items-center justify-center flex-none">
          <ShieldCheck className="w-5 h-5" strokeWidth={2.2} />
        </span>
        <p className="text-sm text-[#0B2545] font-medium">{emptyMessage}</p>
      </motion.section>
    );
  }

  const style = SEVERITY_STYLE[finding.severity] || SEVERITY_STYLE.amber;
  const Icon = ICONS[finding.icon] || AlertTriangle;

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.08 }}
      data-testid={`top-finding-card-${finding.id}`}
      className={`p-6 rounded-2xl border ${style.border} ${style.bg}`}
    >
      <div className="flex items-start gap-4">
        <span
          className={`flex-none w-12 h-12 rounded-lg ${style.icon} flex items-center justify-center`}
        >
          <Icon className="w-6 h-6" strokeWidth={2.2} />
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">
            Top red flag
          </p>
          <p className="mt-2 text-base font-semibold text-[#0B2545] leading-snug">
            <span className="mr-1.5">{style.flag}</span>
            {finding.headline}
          </p>
          <p className="mt-3 text-sm text-[#475569] leading-relaxed">
            {finding.action}
          </p>
          <button
            type="button"
            data-testid={`top-finding-fix-${finding.id}`}
            onClick={() => onFix?.(finding)}
            className="mt-4 h-10 px-5 rounded-lg bg-[#0B2545] text-white text-sm font-semibold hover:bg-[#0B2545]/90 inline-flex items-center"
          >
            Fix this →
          </button>
        </div>
      </div>
    </motion.section>
  );
}
