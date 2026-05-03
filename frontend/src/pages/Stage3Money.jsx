import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Lock } from "lucide-react";
import ProgressBar from "../components/ProgressBar";
import Header from "../components/Header";
import BottomCTA from "../components/BottomCTA";
import KvSlider from "../components/KvSlider";
import { formatINR } from "../lib/currency";
import api from "../lib/api";

// Log-scale conversion for income slider (₹3L → ₹1Cr+).
const incomeBuckets = [
  300000, 500000, 750000, 1000000, 1500000, 2000000, 3000000, 5000000, 7500000, 10000000, 15000000,
];

export default function Stage3Money() {
  const navigate = useNavigate();
  const [incomeIdx, setIncomeIdx] = useState(4); // ₹15L
  const [emis, setEmis] = useState(0);
  const [expenses, setExpenses] = useState(50000);
  const [submitting, setSubmitting] = useState(false);

  const income = incomeBuckets[incomeIdx];

  const handleContinue = async () => {
    setSubmitting(true);
    try {
      await api.patch("/user/me", {
        income,
        emis,
        monthly_expenses: expenses,
      });
      navigate("/audit/policies");
    } catch (e) {
      toast.error("Couldn't save — try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <Header />
      <ProgressBar stage={3} />
      <main className="pt-32 pb-40 md:pb-24 px-6 max-w-xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
            Step 3 of 6 · 15 seconds
          </p>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-[#0B2545] leading-tight">
            A few numbers — sliders only,
            <br />
            no exact figures needed.
          </h1>
        </motion.div>

        <div className="mt-8 space-y-6">
          <section className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card" data-testid="income-section">
            <KvSlider
              testId="income-slider"
              label="Annual income"
              value={incomeIdx}
              onChange={setIncomeIdx}
              min={0}
              max={incomeBuckets.length - 1}
              formatValue={() => formatINR(income, { short: true })}
            />
          </section>

          <section className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card" data-testid="emi-section">
            <KvSlider
              testId="emi-slider"
              label="Major loans / EMIs total"
              value={emis}
              onChange={setEmis}
              min={0}
              max={20000000}
              step={100000}
              formatValue={(v) => (v === 0 ? "None" : formatINR(v, { short: true }))}
              hint="Skip if none. Slide right to add."
            />
          </section>

          <section className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card" data-testid="expenses-section">
            <KvSlider
              testId="expenses-slider"
              label="Monthly household expenses"
              value={expenses}
              onChange={setExpenses}
              min={15000}
              max={500000}
              step={5000}
              formatValue={(v) => formatINR(v, { short: true })}
            />
          </section>
        </div>

        <div className="mt-8 flex items-start gap-3 p-4 rounded-xl bg-[#13A8A8]/5 border border-[#13A8A8]/15">
          <Lock className="w-4 h-4 text-[#13A8A8] mt-0.5 flex-none" strokeWidth={2.2} />
          <p className="text-xs text-[#475569] leading-relaxed">
            We use these only to calculate your ideal cover. They never leave your device unencrypted.
          </p>
        </div>
      </main>

      <BottomCTA testId="stage3-continue" onClick={handleContinue} loading={submitting}>
        Continue
      </BottomCTA>
    </div>
  );
}
