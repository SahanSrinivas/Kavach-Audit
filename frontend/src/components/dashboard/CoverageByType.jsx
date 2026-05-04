import React from "react";
import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { formatINR } from "../../lib/currency";

// Zone B — current vs ideal cover per type, as horizontal bars.
// Color thresholds: ratio >= 75 green, >= 40 amber, else red.
export default function CoverageByType({ rows, onViewAudit }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card"
    >
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Coverage by type</p>
      <h2 className="mt-1 font-heading text-xl font-bold text-[#0B2545]">
        Where you stand vs ideal.
      </h2>
      <div className="mt-5 space-y-3">
        {rows.map((row) => (
          <div key={row.type}>
            <div className="flex justify-between text-sm">
              <span className="font-medium text-[#0B2545]">{row.type}</span>
              <span className="text-[#475569]">
                {formatINR(row.current, { short: true })}{" "}
                <span className="text-[#475569]/70">
                  / {formatINR(row.ideal, { short: true })}
                </span>
              </span>
            </div>
            <div className="mt-1.5 h-2 bg-[#E1E5EB] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  row.ratio >= 75
                    ? "bg-[#0F7B4F]"
                    : row.ratio >= 40
                      ? "bg-[#D97706]"
                      : "bg-[#B22222]"
                }`}
                style={{ width: `${Math.max(2, Math.min(100, row.ratio))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <button
        data-testid="dashboard-view-audit"
        onClick={onViewAudit}
        className="mt-6 text-sm font-semibold text-[#13A8A8] inline-flex items-center gap-1"
      >
        View full audit <ChevronRight className="w-4 h-4" />
      </button>
    </motion.section>
  );
}
