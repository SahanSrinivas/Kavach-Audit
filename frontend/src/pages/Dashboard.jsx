import React from "react";
import { motion } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck, LogOut, Sparkles } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../lib/auth";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const hasAudit = user?.has_audit;

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <header className="border-b border-[#E1E5EB] bg-white">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/dashboard" className="inline-flex items-center gap-2 text-[#0B2545] font-semibold">
            <ShieldCheck className="w-5 h-5 text-[#13A8A8]" strokeWidth={2.5} />
            Kavach
          </Link>
          <div className="flex items-center gap-4">
            <span data-testid="dashboard-user-mobile" className="hidden sm:inline text-sm text-[#475569]">
              +91 {user?.mobile}
            </span>
            <Button
              data-testid="dashboard-logout-button"
              variant="ghost"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="h-9 px-3 text-[#475569] hover:text-[#0B2545]"
            >
              <LogOut className="w-4 h-4 mr-1.5" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-10 md:py-16" data-testid="dashboard-root">
        {!hasAudit ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
            className="text-center max-w-xl mx-auto"
            data-testid="dashboard-empty-state"
          >
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#13A8A8]/10 mb-8">
              <Sparkles className="w-7 h-7 text-[#13A8A8]" strokeWidth={2} />
            </div>
            <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#0B2545]">
              You haven't run your audit yet.
            </h1>
            <p className="mt-4 text-[#475569] text-base sm:text-lg leading-relaxed">
              Takes about 60 seconds. You'll get four scores, the top three red flags in your
              current policies, and a plain-English plan to fix them.
            </p>
            <Button
              data-testid="dashboard-take-audit"
              onClick={() => navigate("/audit/identity")}
              className="mt-10 h-14 px-8 rounded-xl bg-[#0B2545] hover:bg-[#0B2545]/90 text-white font-semibold text-base"
            >
              Take 60-second audit →
            </Button>
            <p className="mt-6 text-xs text-[#475569]">We don't sell. We audit.</p>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            data-testid="dashboard-filled-state"
          >
            <h1 className="font-heading text-3xl font-bold text-[#0B2545]">Your Insurance Console</h1>
            <p className="mt-2 text-[#475569]">Dashboard will populate in Phase 4.</p>
          </motion.div>
        )}
      </main>
    </div>
  );
}
