import React from "react";
import { motion } from "framer-motion";

// Null = engine couldn't score (missing data). Render as neutral grey
// "N/A" — never as red "0", which would imply a failing score.
const colorFor = (score) => {
  if (score === null || score === undefined) return "na";
  return score >= 75 ? "good" : score >= 50 ? "average" : "poor";
};

const STYLES = {
  good: {
    bg: "bg-[#0F7B4F]/8",
    border: "border-[#0F7B4F]/30",
    text: "text-[#0F7B4F]",
  },
  average: {
    bg: "bg-[#D97706]/8",
    border: "border-[#D97706]/30",
    text: "text-[#D97706]",
  },
  poor: {
    bg: "bg-[#B22222]/8",
    border: "border-[#B22222]/30",
    text: "text-[#B22222]",
  },
  na: {
    bg: "bg-[#475569]/5",
    border: "border-[#E1E5EB]",
    text: "text-[#475569]",
  },
};

export default function AuditScoreCard({ icon, label, score, sublabel, testId, onClick, delay = 0 }) {
  const isNa = score === null || score === undefined;
  const style = STYLES[colorFor(score)];
  return (
    <motion.button
      type="button"
      data-testid={testId}
      onClick={onClick}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 1, 0.5, 1] }}
      whileHover={{ y: -2 }}
      className={`text-left p-5 sm:p-6 rounded-xl border ${style.border} ${style.bg} transition-shadow hover:shadow-[0_8px_30px_rgb(11,37,69,0.08)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8]`}
    >
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.15em] text-[#0B2545]">
        <span className="text-base" aria-hidden="true">{icon}</span>
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span data-testid={`${testId}-value`} className={`font-heading text-4xl font-black tracking-tight ${style.text}`}>
          {isNa ? "N/A" : score}
        </span>
        {!isNa && <span className="text-sm font-medium text-[#475569]">/ 100</span>}
      </div>
      <p className={`mt-2 text-sm font-medium ${style.text}`}>{sublabel}</p>
    </motion.button>
  );
}
