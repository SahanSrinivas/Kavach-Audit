import React from "react";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import HeroScore from "./HeroScore";
import ScoreTiles from "./ScoreTiles";
import TopFindingCard from "./TopFindingCard";
import { formatINR } from "../../lib/currency";

// Per-policy detail view (the right side of the Option-C hybrid).
// Reached by tapping a card in PoliciesList; back via the breadcrumb.
//
// Hero score = coverage% computed client-side (sum_insured / ideal),
// because the engine doesn't emit per-policy scores today (gap #8 in
// the IA doc). Cost and gap tiles are dimmed because they're
// portfolio-level by definition. Findings are filtered to those
// related_policy_id-stamped to this policy.

// Maps the engine's coarse policy.type enum to the human label used
// in audit.portfolio.by_type. Keep in sync with the backend's
// _engine_type_for in routers/policies_router.py.
const TYPE_TO_PORTFOLIO_KEY = {
  health: "Health",
  term: "Term Life",
  pa: "Personal Accident",
  motor: "Motor",
  travel: "Travel",
  endowment: "Endowment",
  ci: "Critical Illness",
  home: "Home",
};

function findPortfolioRow(byType, policyType) {
  const expected = TYPE_TO_PORTFOLIO_KEY[String(policyType || "").toLowerCase()];
  if (!expected) return null;
  return byType.find((r) => r.type === expected) || null;
}

function computeCoveragePct(policy, byType) {
  const row = findPortfolioRow(byType, policy.type);
  if (!row || !row.ideal || !policy.sum_insured) return null;
  return Math.min(100, Math.round((policy.sum_insured / row.ideal) * 100));
}

export default function PolicyDetailView({ policy, audit, onBack, onFixFinding }) {
  const byType = audit.portfolio?.by_type || [];
  const coveragePct = computeCoveragePct(policy, byType);
  const findingsForPolicy = (audit.all_findings || []).filter(
    (f) => f.related_policy_id === policy.id,
  );
  const topFinding = findingsForPolicy[0] || null;

  // Coverage is per-policy-computable; claim_readiness shown as the
  // portfolio value (until we have per-policy CR — gap #8).
  // Cost + gap don't make sense at the policy level, so they're dimmed.
  const tileScores = {
    coverage: coveragePct,
    cost: null,
    claim_readiness: audit.scores?.claim_readiness ?? null,
    gap: null,
  };

  const policyTitle = policy.policy_nickname || policy.insurer;
  const productLabel = policy.policy_name || policy.type;

  return (
    <div className="space-y-6" data-testid="policy-detail-view">
      <button
        type="button"
        data-testid="policy-detail-back"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#13A8A8] hover:text-[#0F8888]"
      >
        <ArrowLeft className="w-4 h-4" /> All policies
      </button>

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        data-testid="policy-detail-header"
      >
        <h1 className="font-heading text-2xl font-bold text-[#0B2545]">
          {policyTitle}
        </h1>
        <p className="mt-1 text-sm text-[#475569]">
          {policy.policy_nickname && <>{policy.insurer} · </>}
          {productLabel} · cover {formatINR(policy.sum_insured, { short: true })}
        </p>
      </motion.section>

      <HeroScore
        eyebrow="Coverage for this policy"
        value={coveragePct}
        label={
          coveragePct !== null
            ? `${coveragePct}% of ideal cover`
            : "Can't compute coverage"
        }
        sublabel={
          coveragePct !== null
            ? `You have ${formatINR(policy.sum_insured, { short: true })} of cover. Your profile suggests more.`
            : "We don't have an ideal target for this policy type yet."
        }
      />

      <ScoreTiles
        scores={tileScores}
        breakdowns={audit.breakdowns || {}}
        dimmedScores={["cost", "gap"]}
      />

      {topFinding ? (
        <TopFindingCard finding={topFinding} onFix={onFixFinding} />
      ) : (
        <TopFindingCard
          finding={null}
          emptyMessage="No red flags specific to this policy."
        />
      )}

      <PolicyFacts policy={policy} />
    </div>
  );
}

function PolicyFacts({ policy }) {
  const pf = policy.parsed_fields || {};
  const fields = [
    { l: "Premium", v: `${formatINR(policy.premium)} / yr` },
    policy.end_date && {
      l: "Renews",
      v: new Date(policy.end_date).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }),
    },
    pf.network_hospitals && {
      l: "Network",
      v: `${pf.network_hospitals.toLocaleString("en-IN")} hospitals`,
    },
    pf.room_rent_cap && {
      l: "Room rent cap",
      v: `${formatINR(pf.room_rent_cap)}/day`,
    },
    pf.copay_percent && {
      l: "Co-pay",
      v: `${pf.copay_percent}%`,
    },
    pf.ped_waiting_years && {
      l: "PED waiting",
      v: `${pf.ped_waiting_years} year${pf.ped_waiting_years === 1 ? "" : "s"}`,
    },
  ].filter(Boolean);

  if (fields.length === 0) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.12 }}
      data-testid="policy-detail-facts"
      className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card"
    >
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">
        Policy facts
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
        {fields.map((f) => (
          <div key={f.l}>
            <dt className="text-xs text-[#475569]">{f.l}</dt>
            <dd className="text-sm font-semibold text-[#0B2545]">{f.v}</dd>
          </div>
        ))}
      </dl>
    </motion.section>
  );
}
