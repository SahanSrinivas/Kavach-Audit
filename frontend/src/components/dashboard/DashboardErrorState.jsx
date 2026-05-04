import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { Button } from "../ui/button";

// Top-level error state for when /audit/latest itself failed. Without
// audit data the dashboard can't render anything meaningful — there
// are no scores to display, no portfolio breakdown, no findings — so
// we replace the whole page body with a centered retry rather than a
// shell of blank cards. Matches the visual weight of DashboardEmptyState.
export default function DashboardErrorState({ onRetry, retrying = false }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="text-center max-w-xl mx-auto py-16"
      data-testid="dashboard-error-state"
    >
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#B22222]/10 mb-8">
        <AlertTriangle className="w-7 h-7 text-[#B22222]" strokeWidth={2} />
      </div>
      <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight text-[#0B2545]">
        Couldn't load your audit.
      </h1>
      <p className="mt-4 text-[#475569] text-base leading-relaxed">
        Check your connection and try again. Your data is safe — nothing was
        lost.
      </p>
      <Button
        data-testid="dashboard-error-retry"
        onClick={onRetry}
        disabled={retrying}
        className="mt-8 h-12 px-6 rounded-xl bg-[#0B2545] hover:bg-[#0B2545]/90 text-white font-semibold text-base disabled:opacity-50"
      >
        {retrying ? "Retrying…" : "Retry"}
      </Button>
    </motion.div>
  );
}
