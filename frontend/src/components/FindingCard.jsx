import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, AlertTriangle, ShieldOff, Clock } from "lucide-react";

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

export default function FindingCard({ finding, onFix, onTellMore }) {
  const [expanded, setExpanded] = useState(false);
  const style = SEVERITY_STYLE[finding.severity] || SEVERITY_STYLE.amber;
  const Icon = ICONS[finding.icon] || AlertTriangle;

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      data-testid={`finding-card-${finding.id}`}
      className={`rounded-xl border ${style.border} ${style.bg} overflow-hidden`}
    >
      <button
        type="button"
        data-testid={`finding-toggle-${finding.id}`}
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-4 p-5 text-left"
      >
        <span className={`flex-none w-10 h-10 rounded-lg ${style.icon} flex items-center justify-center`}>
          <Icon className="w-5 h-5" strokeWidth={2.2} />
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#0B2545] leading-snug">
            <span className="mr-1.5">{style.flag}</span>
            {finding.headline}
          </p>
        </div>
        <ChevronDown
          className={`w-5 h-5 text-[#475569] transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="px-5 pb-5"
          >
            <div className="pl-14">
              <p className="text-sm text-[#475569] leading-relaxed">{finding.explanation}</p>
              <p className="mt-4 text-sm font-semibold text-[#0B2545]">{finding.action}</p>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  data-testid={`finding-tell-more-${finding.id}`}
                  onClick={() => onTellMore?.(finding)}
                  className="h-10 px-4 rounded-lg bg-white border border-[#E1E5EB] text-sm font-semibold text-[#0B2545] hover:bg-[#F8FAFC]"
                >
                  Tell me more
                </button>
                <button
                  data-testid={`finding-fix-${finding.id}`}
                  onClick={() => onFix?.(finding)}
                  className="h-10 px-5 rounded-lg bg-[#0B2545] text-white text-sm font-semibold hover:bg-[#0B2545]/90"
                >
                  Fix this →
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
