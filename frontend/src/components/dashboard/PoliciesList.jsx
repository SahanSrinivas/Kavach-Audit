import React from "react";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import PolicyCard from "./PolicyCard";
import SectionError from "./SectionError";

// Zone C — list of the user's policies with a header count + Add button.
// Filters audit findings down to each policy via related_policy_id so
// PolicyCard can render an honest issue chip per row.
//
// onSelectPolicy makes each card tappable; the parent uses it to
// switch into the per-policy detail view.
//
// error/onRetry: when the /policies fetch fails independently of the
// rest of the dashboard, this section renders a SectionError block
// instead of the list. The header "N active" stays hidden in that
// state — we don't know N if the fetch failed.
export default function PoliciesList({
  policies,
  findings = [],
  onAddPolicy,
  onSelectPolicy,
  error = null,
  retrying = false,
  onRetry,
}) {
  if (error) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        data-testid="dashboard-policies"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-4">
          Your policies
        </p>
        <SectionError
          testId="policies-error"
          message="Couldn't load your policies."
          retrying={retrying}
          onRetry={onRetry}
        />
      </motion.section>
    );
  }
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      data-testid="dashboard-policies"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Your policies</p>
          <h2 className="mt-1 font-heading text-xl font-bold text-[#0B2545]">
            {policies.length} active
          </h2>
        </div>
        <button
          data-testid="add-policy-cta"
          onClick={onAddPolicy}
          className="h-10 px-4 rounded-lg bg-white border border-[#E1E5EB] text-sm font-semibold text-[#0B2545] inline-flex items-center gap-1.5 hover:bg-[#F8FAFC]"
        >
          <Plus className="w-4 h-4" /> Add
        </button>
      </div>
      {policies.length === 0 ? (
        <div className="p-6 rounded-xl bg-white border border-dashed border-[#E1E5EB] text-center text-sm text-[#475569]">
          No policies on file yet. Tap Add to upload or declare.
        </div>
      ) : (
        <div className="space-y-3">
          {policies.map((p) => (
            <PolicyCard
              key={p.id}
              policy={p}
              findingsForPolicy={findings.filter(
                (f) => f.related_policy_id === p.id,
              )}
              onSelect={onSelectPolicy}
            />
          ))}
        </div>
      )}
    </motion.section>
  );
}
