import React from "react";
import { motion } from "framer-motion";
import { formatINR } from "../../lib/currency";

// Zone A — top stat strip. 2-up on mobile, 4-up on md+.
// Reads audit.portfolio: total_cover, total_premium, active_policies, next_renewal.
export default function PortfolioHeader({ portfolio }) {
  const stats = [
    { l: "Total cover", v: formatINR(portfolio.total_cover, { short: true }) },
    { l: "Annual premium", v: formatINR(portfolio.total_premium) },
    { l: "Active policies", v: portfolio.active_policies },
    {
      l: "Next renewal",
      v: portfolio.next_renewal
        ? new Date(portfolio.next_renewal).toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
          })
        : "—",
    },
  ];

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid grid-cols-2 md:grid-cols-4 gap-3"
      data-testid="portfolio-header"
    >
      {stats.map((s, i) => (
        <div key={i} className="p-5 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">{s.l}</p>
          <p className="mt-1.5 font-heading text-2xl font-bold text-[#0B2545]">{s.v}</p>
        </div>
      ))}
    </motion.section>
  );
}
