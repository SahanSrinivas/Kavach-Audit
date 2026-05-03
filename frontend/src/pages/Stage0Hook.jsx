import React from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ShieldCheck, ArrowRight } from "lucide-react";

export default function Stage0Hook() {
  const navigate = useNavigate();
  return (
    <div className="min-h-[100dvh] flex flex-col bg-gradient-to-br from-[#0B2545]/[0.04] via-[#F8FAFC] to-[#13A8A8]/[0.06]">
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16 max-w-3xl mx-auto w-full">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.25, 1, 0.5, 1] }}
          className="w-full"
        >
          <div
            data-testid="brand-mark"
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-[#E1E5EB] text-xs font-semibold tracking-widest uppercase text-[#13A8A8] mb-10"
          >
            <ShieldCheck className="w-3.5 h-3.5" strokeWidth={2.5} />
            Kavach
          </div>

          <h1
            data-testid="hero-headline"
            className="font-heading text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter text-[#0B2545] leading-[1.02]"
          >
            Find out if your insurance
            <br />
            is <span className="text-[#13A8A8]">actually protecting</span> you.
          </h1>

          <p
            data-testid="hero-subtext"
            className="mt-6 text-base sm:text-lg text-[#475569] max-w-xl leading-relaxed"
          >
            Free 60-second audit. No signup. No sales calls.
          </p>

          <motion.button
            data-testid="start-audit-button"
            onClick={() => navigate("/audit/identity")}
            whileTap={{ scale: 0.98 }}
            className="mt-10 group inline-flex items-center gap-3 h-14 px-8 rounded-xl bg-[#0B2545] hover:bg-[#0B2545]/90 text-white font-semibold text-base transition-colors shadow-[0_8px_30px_rgb(11,37,69,0.15)]"
          >
            Start Audit
            <ArrowRight className="w-5 h-5 transition-transform group-hover:translate-x-0.5" strokeWidth={2.5} />
          </motion.button>

          <p data-testid="hero-reassurance" className="mt-6 text-sm text-[#475569]">
            We don't sell insurance. We tell you if yours is any good.
          </p>
        </motion.div>
      </main>

      <footer className="px-6 py-6 text-center">
        <a
          href="/login"
          data-testid="stage0-login-link"
          className="text-sm text-[#475569] hover:text-[#0B2545] transition-colors"
        >
          Already audited? <span className="underline underline-offset-4">Sign in</span>
        </a>
      </footer>
    </div>
  );
}
