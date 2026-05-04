import React, { useState } from "react";
import { motion } from "framer-motion";
import ScoreBreakdownDrawer from "./ScoreBreakdownDrawer";

// 4-tile score grid (zone B). 2-up on mobile, 4-up on md+. Tap any tile
// to open the breakdown drawer.
//
// Empty values: when the engine returns null for a score (e.g. cost
// needs ≥2 policies, claim_readiness needs a health policy), the tile
// shows "—" with a one-line reason — never invent a number.
//
// Policy-detail mode: pass dimmedScores=["cost", "gap"] to render
// those two tiles greyed out + labelled "portfolio-level". They stay
// non-clickable because the underlying breakdown isn't per-policy.

const SCORE_ORDER = ["coverage", "cost", "claim_readiness", "gap"];

const SCORE_LABEL = {
  coverage: "Coverage",
  cost: "Cost",
  claim_readiness: "Claim ready",
  gap: "Gap",
};

const NULL_REASON = {
  coverage: "Upload policies",
  cost: "Need 2+ policies",
  claim_readiness: "Need a health policy",
  gap: "—",
};

function scoreColor(value) {
  if (value === null || value === undefined) return "#94A3B8";
  if (value >= 75) return "#0F7B4F";
  if (value >= 50) return "#D97706";
  return "#B22222";
}

export default function ScoreTiles({ scores, breakdowns = {}, dimmedScores = [] }) {
  const [openScoreKey, setOpenScoreKey] = useState(null);

  return (
    <>
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.04 }}
        data-testid="score-tiles"
        className="grid grid-cols-2 md:grid-cols-4 gap-3"
      >
        {SCORE_ORDER.map((key) => {
          const value = scores?.[key] ?? null;
          const isDimmed = dimmedScores.includes(key);
          const color = scoreColor(value);
          const clickable = !isDimmed && value !== null;

          return (
            <button
              key={key}
              type="button"
              data-testid={`score-tile-${key}`}
              disabled={!clickable}
              onClick={() => setOpenScoreKey(key)}
              className={`text-left p-4 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card transition-colors ${
                clickable ? "hover:border-[#13A8A8]/40" : "cursor-default"
              } ${isDimmed ? "opacity-50" : ""}`}
            >
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">
                {SCORE_LABEL[key]}
              </p>
              <p
                className="mt-1.5 font-heading text-3xl font-bold"
                style={{ color: value === null ? "#94A3B8" : color }}
              >
                {value === null ? "—" : value}
              </p>
              <p className="mt-1 text-[11px] text-[#475569] leading-tight min-h-[26px]">
                {isDimmed
                  ? "portfolio-level"
                  : value === null
                    ? NULL_REASON[key]
                    : "tap to see how"}
              </p>
            </button>
          );
        })}
      </motion.section>

      <ScoreBreakdownDrawer
        open={openScoreKey !== null}
        onOpenChange={(o) => {
          if (!o) setOpenScoreKey(null);
        }}
        scoreKey={openScoreKey}
        breakdown={openScoreKey ? breakdowns[openScoreKey] : null}
      />
    </>
  );
}
