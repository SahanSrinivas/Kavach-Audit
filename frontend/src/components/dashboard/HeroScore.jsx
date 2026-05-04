import React from "react";
import { motion } from "framer-motion";
import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

// Single big number with a radial gauge. Used in two places:
//   - Portfolio view: gap score (engine's headline summary)
//   - Policy detail view: per-policy coverage% (frontend-computed)
//
// The two contexts pass different eyebrow/label text but the chart
// itself is the same — one ring, one number, color thresholded.
//
// Color thresholds match CoverageByType for consistency: ≥75 green,
// ≥50 amber, else red. Null values render the empty ring + "—".

function scoreColor(value) {
  if (value === null || value === undefined) return "#94A3B8";
  if (value >= 75) return "#0F7B4F";
  if (value >= 50) return "#D97706";
  return "#B22222";
}

export default function HeroScore({ eyebrow, label, sublabel, value, footer }) {
  const color = scoreColor(value);
  // Recharts needs non-null data; the visible center text handles null.
  const data = [{ value: value ?? 0, fill: color }];

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="hero-score"
      className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card"
    >
      {eyebrow && (
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">
          {eyebrow}
        </p>
      )}
      <div className="mt-4 flex items-center gap-5">
        <div className="relative w-[140px] h-[140px] flex-none">
          <RadialBarChart
            width={140}
            height={140}
            innerRadius="75%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            data={data}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, 100]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBar
              background={{ fill: "#E1E5EB" }}
              dataKey="value"
              angleAxisId={0}
              cornerRadius={8}
            />
          </RadialBarChart>
          <div
            data-testid="hero-score-value"
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
          >
            <span
              className="font-heading text-3xl font-bold"
              style={{ color }}
            >
              {value === null || value === undefined ? "—" : value}
            </span>
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-heading text-xl font-bold text-[#0B2545] leading-tight">
            {label}
          </p>
          {sublabel && (
            <p className="mt-1.5 text-sm text-[#475569] leading-snug">
              {sublabel}
            </p>
          )}
          {footer && (
            <p className="mt-3 text-xs text-[#475569]">{footer}</p>
          )}
        </div>
      </div>
    </motion.section>
  );
}
