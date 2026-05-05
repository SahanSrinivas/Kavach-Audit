import React, { useId, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, FileText, Upload } from "lucide-react";
import Header from "../components/Header";
import LifeTrustPanel from "../components/life/LifeTrustPanel";
import { LIFE_INSURER_STATS_SAMPLE } from "@/data/lifeInsurerStats";

export default function LifeAuditStart() {
  const formId = useId();
  const [insurerId, setInsurerId] = useState(LIFE_INSURER_STATS_SAMPLE[0]?.id ?? "");
  const [cisFile, setCisFile] = useState(null);
  const [bondFile, setBondFile] = useState(null);

  return (
    <div className="min-h-[100dvh] flex flex-col bg-gradient-to-br from-[#0B2545]/[0.04] via-[#F8FAFC] to-[#13A8A8]/[0.06]">
      <Header />

      <main className="flex-1 w-full max-w-3xl mx-auto px-6 pt-24 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.25, 1, 0.5, 1] }}
        >
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#13A8A8]">Life insurance audit</p>
          <h1
            className="mt-3 font-heading text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight text-[#0B2545] leading-[1.08]"
            data-testid="life-audit-headline"
          >
            Decode what your{" "}
            <span className="text-[#13A8A8]">policy bond &amp; CIS</span> actually say.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-[#475569] leading-relaxed">
            Commission-neutral audit path for Indian life cover: IRDAI-style trust signals, then your issued documents
            (Customer Information Sheet + policy bond)—the same evidence-led approach as our health audit.
          </p>

          <div className="mt-10 rounded-2xl border border-[#E1E5EB] bg-white p-5 sm:p-6 shadow-sm">
            <LifeTrustPanel selectedId={insurerId} onSelectId={setInsurerId} />
          </div>

          <section className="mt-12" aria-labelledby={`${formId}-docs`}>
            <h2 id={`${formId}-docs`} className="font-heading text-xl font-bold text-[#0B2545]">
              Bring your issued documents
            </h2>
            <p className="mt-2 text-sm text-[#64748B] leading-relaxed">
              Upload PDFs or clear photos. Parsing &amp; structured &ldquo;Life Schedule&rdquo; extraction ships next;
              we store filenames locally in this beta screen only.
            </p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col rounded-xl border-2 border-dashed border-[#E1E5EB] bg-[#F8FAFC] p-4 cursor-pointer hover:border-[#13A8A8]/50 transition-colors">
                <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#0B2545]">
                  <FileText className="w-4 h-4 text-[#13A8A8]" aria-hidden="true" />
                  Customer Information Sheet (CIS)
                </span>
                <span className="mt-2 text-xs text-[#64748B]">IRDAI-mandated simple-language summary</span>
                <input
                  type="file"
                  accept="application/pdf,image/*"
                  className="sr-only"
                  onChange={(e) => setCisFile(e.target.files?.[0] ?? null)}
                />
                <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[#13A8A8]">
                  <Upload className="w-3.5 h-3.5" aria-hidden="true" />
                  {cisFile ? cisFile.name : "Choose file"}
                </span>
              </label>
              <label className="flex flex-col rounded-xl border-2 border-dashed border-[#E1E5EB] bg-[#F8FAFC] p-4 cursor-pointer hover:border-[#13A8A8]/50 transition-colors">
                <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#0B2545]">
                  <FileText className="w-4 h-4 text-[#13A8A8]" aria-hidden="true" />
                  Policy bond / certificate
                </span>
                <span className="mt-2 text-xs text-[#64748B]">Issued contract after underwriting</span>
                <input
                  type="file"
                  accept="application/pdf,image/*"
                  className="sr-only"
                  onChange={(e) => setBondFile(e.target.files?.[0] ?? null)}
                />
                <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[#13A8A8]">
                  <Upload className="w-3.5 h-3.5" aria-hidden="true" />
                  {bondFile ? bondFile.name : "Choose file"}
                </span>
              </label>
            </div>
          </section>

          <div className="mt-10 flex flex-col sm:flex-row gap-3 sm:items-center">
            <button
              type="button"
              disabled
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#0B2545]/40 px-6 text-white font-semibold text-sm cursor-not-allowed"
              title="Extraction pipeline coming next"
            >
              Continue to Life Schedule
              <ArrowRight className="w-4 h-4" strokeWidth={2.5} aria-hidden="true" />
            </button>
            <p className="text-xs text-[#64748B] sm:max-w-xs">
              Button activates when CIS/bond extraction is wired to the audit engine (see spec).
            </p>
          </div>

          <p className="mt-10 text-sm text-[#475569]">
            Looking for <span className="font-medium text-[#0B2545]">health</span> instead?{" "}
            <Link to="/audit/start" className="text-[#13A8A8] font-semibold underline underline-offset-4">
              Start the health audit
            </Link>
            .
          </p>
        </motion.div>
      </main>

      <footer className="px-6 py-6 text-center border-t border-[#E1E5EB] bg-white/80">
        <Link to="/" className="text-sm text-[#475569] hover:text-[#0B2545] transition-colors">
          ← Back to home
        </Link>
        {" · "}
        <a href="/login" className="text-sm text-[#475569] hover:text-[#0B2545] underline underline-offset-4">
          Sign in
        </a>
      </footer>
    </div>
  );
}
