import React, { useEffect, useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, FileText, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import Header from "../components/Header";
import LifeTrustPanel from "../components/life/LifeTrustPanel";
import { fetchLifeStatsBundle, fetchLifeStatsIndex, normalizeInsurerRow } from "@/lib/lifeStats";
import api from "@/lib/api";

const SCHEDULE_STORAGE_KEY = "kavachly_life_schedule_v1";

export default function LifeAuditStart() {
  const formId = useId();
  const navigate = useNavigate();
  const [insurerId, setInsurerId] = useState("");
  const [rows, setRows] = useState([]);
  const [fyLabel, setFyLabel] = useState("");
  const [availableFys, setAvailableFys] = useState([]);
  const [selectedFy, setSelectedFy] = useState("");
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState(null);

  const [cisFile, setCisFile] = useState(null);
  const [bondFile, setBondFile] = useState(null);
  const [extracting, setExtracting] = useState(false);

  const applyBundle = (bundle, fyKey) => {
    const normalized = (bundle.insurers || []).map(normalizeInsurerRow);
    setRows(normalized);
    setFyLabel(bundle.fyLabel || `FY ${fyKey}`);
    setInsurerId((prev) => {
      if (normalized.some((r) => r.id === prev)) return prev;
      return normalized[0]?.id ?? "";
    });
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setStatsLoading(true);
      setStatsError(null);
      try {
        const index = await fetchLifeStatsIndex();
        const fys = index.availableFys || [];
        const def = index.defaultFy || fys[0];
        if (cancelled) return;
        setAvailableFys(fys);
        setSelectedFy(def);
        const bundle = await fetchLifeStatsBundle(def);
        if (cancelled) return;
        applyBundle(bundle, def);
      } catch (e) {
        if (!cancelled) {
          setStatsError(e?.message || "Could not load life insurer statistics.");
          setRows([]);
        }
      } finally {
        if (!cancelled) setStatsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onFyChange = async (fy) => {
    setSelectedFy(fy);
    setStatsLoading(true);
    setStatsError(null);
    try {
      const bundle = await fetchLifeStatsBundle(fy);
      applyBundle(bundle, fy);
    } catch (e) {
      toast.error(e?.message || "Failed to load FY bundle.");
      setStatsError(e?.message || "FY load failed.");
    } finally {
      setStatsLoading(false);
    }
  };

  const canContinue = cisFile && bondFile && !extracting;

  const handleContinue = async () => {
    if (!cisFile || !bondFile) return;
    setExtracting(true);
    try {
      const fd = new FormData();
      fd.append("cis", cisFile);
      fd.append("bond", bondFile);
      fd.append("insurer_id", insurerId || "");
      const res = await api.post("/life/extract", fd);
      const payload = res.data?.data;
      if (!res.data?.success || !payload) {
        throw new Error(res.data?.error || "Extraction failed.");
      }
      try {
        sessionStorage.setItem(SCHEDULE_STORAGE_KEY, JSON.stringify(payload));
      } catch (err) {
        toast.error("Could not save results in this browser session.");
        return;
      }
      toast.success("Life Schedule extracted — review the fields.");
      navigate("/audit/life/schedule");
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || d).join(", ")
            : e.message;
      toast.error(msg || "Could not extract from PDFs. Use text-based PDFs if possible.");
    } finally {
      setExtracting(false);
    }
  };

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
            <LifeTrustPanel
              selectedId={insurerId}
              onSelectId={setInsurerId}
              rows={rows}
              fyLabel={fyLabel}
              loading={statsLoading}
              error={statsError}
              selectedFy={selectedFy}
              onSelectFy={onFyChange}
              availableFys={availableFys}
            />
          </div>

          <section className="mt-12" aria-labelledby={`${formId}-docs`}>
            <h2 id={`${formId}-docs`} className="font-heading text-xl font-bold text-[#0B2545]">
              Bring your issued documents
            </h2>
            <p className="mt-2 text-sm text-[#64748B] leading-relaxed">
              Upload PDFs (text-based work best). We extract a structured Life Schedule using on-device text heuristics on
              the server—no LLM in this path.
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
                  accept="application/pdf"
                  className="sr-only"
                  onChange={(e) => setCisFile(e.target.files?.[0] ?? null)}
                />
                <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[#13A8A8] break-all">
                  <Upload className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  {cisFile ? cisFile.name : "Choose PDF"}
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
                  accept="application/pdf"
                  className="sr-only"
                  onChange={(e) => setBondFile(e.target.files?.[0] ?? null)}
                />
                <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[#13A8A8] break-all">
                  <Upload className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  {bondFile ? bondFile.name : "Choose PDF"}
                </span>
              </label>
            </div>
          </section>

          <div className="mt-10 flex flex-col sm:flex-row gap-3 sm:items-center">
            <button
              type="button"
              disabled={!canContinue}
              onClick={handleContinue}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#0B2545] px-6 text-white font-semibold text-sm shadow-sm hover:bg-[#0B2545]/90 transition-colors disabled:bg-[#0B2545]/40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2"
            >
              {extracting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  Extracting…
                </>
              ) : (
                <>
                  Continue to Life Schedule
                  <ArrowRight className="w-4 h-4" strokeWidth={2.5} aria-hidden="true" />
                </>
              )}
            </button>
            <p className="text-xs text-[#64748B] sm:max-w-xs">
              Requires both PDFs and a running API ({process.env.REACT_APP_BACKEND_URL || "set REACT_APP_BACKEND_URL"}).
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
