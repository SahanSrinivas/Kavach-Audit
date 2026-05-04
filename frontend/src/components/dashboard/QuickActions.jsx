import React from "react";
import { motion } from "framer-motion";
import { UserPlus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api from "../../lib/api";

// Zone E (G in the new IA) — Add member + Re-audit CTAs.
// Re-audit handler is self-contained: posts /audit/generate, toasts,
// reloads the page. Caller handles the Add-member modal via prop.
export default function QuickActions({ onAddMember }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="grid grid-cols-1 sm:grid-cols-2 gap-4"
    >
      <button
        data-testid="add-member-cta"
        onClick={onAddMember}
        className="p-5 rounded-2xl bg-white border border-[#E1E5EB] text-left hover:border-[#13A8A8]/40"
      >
        <UserPlus className="w-6 h-6 text-[#13A8A8] mb-3" />
        <p className="font-semibold text-[#0B2545]">Add a household member</p>
        <p className="mt-1 text-sm text-[#475569]">Invite spouse, parents or kids. Household view unlocks.</p>
      </button>
      <button
        data-testid="reaudit-cta-dashboard"
        onClick={async () => {
          await api.post("/audit/generate");
          toast.success("Re-audit complete");
          window.location.reload();
        }}
        className="p-5 rounded-2xl bg-white border border-[#E1E5EB] text-left hover:border-[#13A8A8]/40"
      >
        <RefreshCw className="w-6 h-6 text-[#13A8A8] mb-3" />
        <p className="font-semibold text-[#0B2545]">Re-run my audit</p>
        <p className="mt-1 text-sm text-[#475569]">Anything changed? Get fresh scores in 30 seconds.</p>
      </button>
    </motion.section>
  );
}
