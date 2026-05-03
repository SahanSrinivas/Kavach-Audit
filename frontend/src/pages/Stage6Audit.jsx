import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Share2, Download, ShieldCheck, ChevronRight, RefreshCw } from "lucide-react";
import html2canvas from "html2canvas";
import { toast } from "sonner";
import AuditScoreCard from "../components/AuditScoreCard";
import FindingCard from "../components/FindingCard";
import { formatINR } from "../lib/currency";
import api from "../lib/api";

const SCORE_LABEL = (key, score) => {
  if (key === "coverage") {
    if (score >= 75) return "Adequate";
    return score >= 50 ? "Underinsured" : `Severely underinsured`;
  }
  if (key === "cost") return score >= 75 ? "Reasonably priced" : score >= 50 ? "Slightly overpriced" : "Overpaying ~22%";
  if (key === "claim_readiness")
    return score >= 75 ? "Clean" : score >= 50 ? "Some red flags" : "Multiple red flags";
  return score >= 75 ? "Well-protected" : score >= 50 ? "1 critical gap" : "Critical gaps";
};

export default function Stage6Audit() {
  const navigate = useNavigate();
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const shareRef = useRef(null);
  const [tellMore, setTellMore] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/audit/latest");
        setAudit(r.data?.data?.audit || null);
      } catch (_) {
        toast.error("Couldn't load audit");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleFix = (finding) => {
    navigate(`/recommendations?finding_id=${finding.id}`);
  };

  const handleShare = async () => {
    if (!shareRef.current) return;
    try {
      const canvas = await html2canvas(shareRef.current, {
        backgroundColor: "#F8FAFC",
        scale: 2,
      });
      const blob = await new Promise((res) => canvas.toBlob(res, "image/png"));
      const file = new File([blob], "kavach-audit.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          title: "My Kavach Audit",
          text: "Just audited my insurance with Kavach.",
          files: [file],
        });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "kavach-audit.png";
        a.click();
        URL.revokeObjectURL(url);
        toast.success("Audit card downloaded");
      }
    } catch (e) {
      toast.error("Couldn't generate share image");
    }
  };

  if (loading) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin" />
      </div>
    );
  }
  if (!audit) return null;

  const { scores, findings, portfolio } = audit;

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC] pb-16">
      <header className="sticky top-0 z-20 bg-[#F8FAFC]/90 backdrop-blur-md border-b border-[#E1E5EB]/60">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="inline-flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[#13A8A8]" strokeWidth={2.5} />
            <span className="font-heading font-semibold text-[#0B2545]">Your Audit</span>
          </div>
          <button
            data-testid="audit-go-dashboard"
            onClick={() => navigate("/dashboard")}
            className="text-sm font-semibold text-[#475569] hover:text-[#0B2545] inline-flex items-center gap-1"
          >
            Dashboard <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8" data-testid="audit-root">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Your scores</p>
          <h1 className="mt-1 font-heading text-3xl sm:text-4xl font-bold text-[#0B2545]">
            Here's the truth about your insurance.
          </h1>
        </motion.div>

        {/* Section A — Score cards */}
        <div ref={shareRef} className="mt-6 p-6 rounded-2xl bg-[#F8FAFC]" data-testid="audit-share-card">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <AuditScoreCard
              testId="score-coverage"
              icon="🛡️"
              label="Coverage"
              score={scores.coverage}
              sublabel={SCORE_LABEL("coverage", scores.coverage)}
              delay={0.05}
            />
            <AuditScoreCard
              testId="score-cost"
              icon="💰"
              label="Cost"
              score={scores.cost}
              sublabel={SCORE_LABEL("cost", scores.cost)}
              delay={0.1}
            />
            <AuditScoreCard
              testId="score-claim"
              icon="🎯"
              label="Claim-readiness"
              score={scores.claim_readiness}
              sublabel={SCORE_LABEL("claim_readiness", scores.claim_readiness)}
              delay={0.15}
            />
            <AuditScoreCard
              testId="score-gap"
              icon="📊"
              label="Gap"
              score={scores.gap}
              sublabel={SCORE_LABEL("gap", scores.gap)}
              delay={0.2}
            />
          </div>
          <p className="mt-4 text-[10px] tracking-widest uppercase text-[#475569] text-center font-semibold">
            kavach · audited in 60 seconds
          </p>
        </div>

        {/* Findings */}
        <section className="mt-12">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#B22222]">Top 3 findings</p>
          <h2 className="mt-1 font-heading text-2xl font-bold text-[#0B2545]">
            Where your policy is leaking.
          </h2>
          <div className="mt-5 space-y-3">
            {findings.map((f) => (
              <FindingCard
                key={f.id}
                finding={f}
                onFix={handleFix}
                onTellMore={setTellMore}
              />
            ))}
          </div>
        </section>

        {/* Portfolio */}
        {portfolio && (
          <section className="mt-12" data-testid="audit-portfolio">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Portfolio</p>
            <h2 className="mt-1 font-heading text-2xl font-bold text-[#0B2545]">
              What you have today.
            </h2>
            <div className="mt-5 grid grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                { l: "Total cover", v: formatINR(portfolio.total_cover, { short: true }) },
                { l: "Annual premium", v: formatINR(portfolio.total_premium) },
                { l: "Active policies", v: portfolio.active_policies },
                {
                  l: "Next renewal",
                  v: portfolio.next_renewal
                    ? new Date(portfolio.next_renewal).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
                    : "—",
                },
              ].map((s, i) => (
                <div key={i} className="p-4 rounded-xl bg-white border border-[#E1E5EB]">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">{s.l}</p>
                  <p className="mt-1 font-heading text-xl font-bold text-[#0B2545]">{s.v}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 p-5 rounded-xl bg-white border border-[#E1E5EB]">
              <p className="text-sm font-semibold text-[#0B2545] mb-4">Coverage by type</p>
              <div className="space-y-3">
                {portfolio.by_type.map((row) => (
                  <div key={row.type}>
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-[#0B2545]">{row.type}</span>
                      <span className="text-[#475569]">
                        {formatINR(row.current, { short: true })}{" "}
                        <span className="text-[#475569]/70">/ {formatINR(row.ideal, { short: true })}</span>
                      </span>
                    </div>
                    <div className="mt-1.5 h-2 bg-[#E1E5EB] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          row.ratio >= 75 ? "bg-[#0F7B4F]" : row.ratio >= 40 ? "bg-[#D97706]" : "bg-[#B22222]"
                        }`}
                        style={{ width: `${Math.max(2, Math.min(100, row.ratio))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Share + actions */}
        <section className="mt-12 flex flex-wrap gap-3">
          <button
            data-testid="share-audit"
            onClick={handleShare}
            className="h-12 px-5 rounded-xl bg-[#0B2545] text-white font-semibold inline-flex items-center gap-2 hover:bg-[#0B2545]/90"
          >
            <Share2 className="w-4 h-4" /> Share my audit
          </button>
          <button
            data-testid="reaudit-cta"
            onClick={async () => {
              try {
                await api.post("/audit/generate");
                window.location.reload();
              } catch (_) {}
            }}
            className="h-12 px-5 rounded-xl bg-white border border-[#E1E5EB] text-[#0B2545] font-semibold inline-flex items-center gap-2 hover:bg-[#F8FAFC]"
          >
            <RefreshCw className="w-4 h-4" /> Re-run audit
          </button>
        </section>
      </main>

      {/* Tell-me-more modal */}
      {tellMore && (
        <div
          className="fixed inset-0 z-50 bg-[#0B2545]/40 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
          onClick={() => setTellMore(null)}
          data-testid="tellmore-modal"
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl max-w-lg w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
              Why this matters
            </p>
            <h3 className="font-heading text-xl font-bold text-[#0B2545]">{tellMore.headline}</h3>
            <p className="mt-3 text-sm text-[#475569] leading-relaxed">{tellMore.explanation}</p>
            <p className="mt-4 text-sm font-semibold text-[#0B2545]">What to do</p>
            <p className="text-sm text-[#475569] leading-relaxed">{tellMore.action}</p>
            <div className="mt-6 flex gap-3 justify-end">
              <button
                data-testid="tellmore-close"
                onClick={() => setTellMore(null)}
                className="h-10 px-4 rounded-lg border border-[#E1E5EB] text-sm font-semibold text-[#0B2545] hover:bg-[#F8FAFC]"
              >
                Got it
              </button>
              <button
                onClick={() => {
                  setTellMore(null);
                  handleFix(tellMore);
                }}
                className="h-10 px-5 rounded-lg bg-[#0B2545] text-white text-sm font-semibold hover:bg-[#0B2545]/90"
              >
                Fix this →
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
