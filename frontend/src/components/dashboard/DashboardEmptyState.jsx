import React from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { Button } from "../ui/button";

// Shown when user.has_audit is false. Single CTA → onTakeAudit().
export default function DashboardEmptyState({ onTakeAudit }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="text-center max-w-xl mx-auto py-16"
      data-testid="dashboard-empty-state"
    >
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#13A8A8]/10 mb-8">
        <Sparkles className="w-7 h-7 text-[#13A8A8]" strokeWidth={2} />
      </div>
      <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#0B2545]">
        You haven't run your audit yet.
      </h1>
      <p className="mt-4 text-[#475569] text-base sm:text-lg leading-relaxed">
        Takes about 60 seconds. You'll get four scores, the top three red flags in your current
        policies, and a plain-English plan to fix them.
      </p>
      <Button
        data-testid="dashboard-take-audit"
        onClick={onTakeAudit}
        className="mt-10 h-14 px-8 rounded-xl bg-[#0B2545] hover:bg-[#0B2545]/90 text-white font-semibold text-base"
      >
        Take 60-second audit →
      </Button>
      <p className="mt-6 text-xs text-[#475569]">We don't sell. We audit.</p>
    </motion.div>
  );
}
