import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  UploadCloud,
  PencilLine,
  SkipForward,
  FileText,
  CheckCircle2,
  Loader2,
  Building2,
  IndianRupee,
} from "lucide-react";
import ProgressBar from "../components/ProgressBar";
import Header from "../components/Header";
import BottomCTA from "../components/BottomCTA";
import KvSlider from "../components/KvSlider";
import { formatINR } from "../lib/currency";
import api from "../lib/api";
import FieldConfidenceBadge from "@/components/shared/FieldConfidenceBadge";

const PARSE_HINTS = [
  "Reading sub-limits…",
  "Checking exclusions…",
  "Calculating claim-risk…",
  "Comparing to market…",
];

// Rotating placeholders for the nickname input. Examples mirror typical
// Indian household scenarios so the user immediately gets the idea.
const NICKNAME_PLACEHOLDERS = [
  "Father's policy",
  "My office policy",
  "Wife's HDFC plan",
];
const NICKNAME_MAX_LEN = 60;

const HEALTH_INSURERS = [
  "HDFC ERGO General Insurance",
  "ICICI Lombard",
  "Star Health & Allied Insurance",
  "Niva Bupa (Max Bupa)",
  "Care Health Insurance",
  "Aditya Birla Health Insurance",
  "Bajaj Allianz General Insurance",
  "Tata AIG General Insurance",
  "Manipal Cigna",
  "Reliance General Insurance",
];
const TERM_INSURERS = ["LIC", "HDFC Life", "ICICI Prudential", "Max Life", "Tata AIA Life", "SBI Life"];

function PathCard({ active, badge, icon: Icon, title, body, testId, onClick }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`text-left w-full rounded-xl border-2 p-5 transition-all ${
        active
          ? "border-[#0B2545] bg-[#0B2545]/[0.04] shadow-sm"
          : "border-[#E1E5EB] bg-white hover:border-[#13A8A8]/40 hover:bg-[#F8FAFC]"
      }`}
    >
      {badge && (
        <span className="inline-block text-[10px] font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-2">
          {badge}
        </span>
      )}
      <div className="flex items-start gap-3">
        <span className="w-10 h-10 rounded-lg bg-[#13A8A8]/10 flex items-center justify-center flex-none">
          <Icon className="w-5 h-5 text-[#13A8A8]" strokeWidth={2.2} />
        </span>
        <div>
          <p className="font-semibold text-[#0B2545]">{title}</p>
          <p className="text-sm text-[#475569] mt-0.5 leading-relaxed">{body}</p>
        </div>
      </div>
    </button>
  );
}

function ParsingFile({ file }) {
  const [hintIdx, setHintIdx] = useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setHintIdx((i) => (i + 1) % PARSE_HINTS.length), 1500);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="flex items-center gap-3 p-4 rounded-lg bg-white border border-[#E1E5EB]">
      <Loader2 className="w-5 h-5 text-[#13A8A8] animate-spin flex-none" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[#0B2545] truncate">{file.name}</p>
        <p className="text-xs text-[#475569]">{PARSE_HINTS[hintIdx]}</p>
      </div>
    </div>
  );
}

function ParsedPolicyCard({ policy }) {
  const uiList = policy.parser_output?.field_confidence_ui ?? [];
  const uiByKey = Object.fromEntries(uiList.map((row) => [row.fieldKey, row]));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="p-5 rounded-xl bg-white border border-[#0F7B4F]/30 kv-shadow-card"
      data-testid={`parsed-policy-${policy.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.15em] text-[#0F7B4F]">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Parsed
          </div>
          <p className="mt-1.5 font-semibold text-[#0B2545]">{policy.insurer}</p>
          <p className="text-sm text-[#475569]">{policy.policy_name}</p>
        </div>
        <Building2 className="w-8 h-8 text-[#13A8A8]/60" strokeWidth={1.4} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 pt-4 border-t border-[#E1E5EB]">
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">Sum insured</p>
            {uiByKey.sum_insured ? (
              <FieldConfidenceBadge
                tier={uiByKey.sum_insured.tier}
                score={typeof uiByKey.sum_insured.score === "number" ? uiByKey.sum_insured.score : null}
                verifyInPdf={uiByKey.sum_insured.verifyInPdf}
              />
            ) : null}
          </div>
          <p className="font-heading text-lg font-bold text-[#0B2545]">
            {formatINR(policy.sum_insured, { short: true })}
          </p>
        </div>
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">Annual premium</p>
            {uiByKey.premium_annual ? (
              <FieldConfidenceBadge
                tier={uiByKey.premium_annual.tier}
                score={typeof uiByKey.premium_annual.score === "number" ? uiByKey.premium_annual.score : null}
                verifyInPdf={uiByKey.premium_annual.verifyInPdf}
              />
            ) : null}
          </div>
          <p className="font-heading text-lg font-bold text-[#0B2545]">{formatINR(policy.premium)}</p>
        </div>
      </div>
    </motion.div>
  );
}

export default function Stage4Policies() {
  const navigate = useNavigate();
  const [path, setPath] = useState(""); // "" | upload | declare | skip
  const [submitting, setSubmitting] = useState(false);

  // Upload state
  const fileInputRef = useRef();
  const [uploading, setUploading] = useState([]); // [{name}]
  const [parsedPolicies, setParsedPolicies] = useState([]);
  // Existing-policy count (from prior sessions). Loaded once on mount;
  // determines whether the nickname field is required (>= 1 → required).
  const [existingPolicyCount, setExistingPolicyCount] = useState(0);
  // Nickname input + rotating placeholder
  const [nickname, setNickname] = useState("");
  const [nicknamePlaceholderIdx, setNicknamePlaceholderIdx] = useState(0);

  useEffect(() => {
    api.get("/policies")
      .then((r) => setExistingPolicyCount(r.data?.data?.policies?.length || 0))
      .catch(() => setExistingPolicyCount(0));   // default-safe — hint UX, not gate
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setNicknamePlaceholderIdx((i) => (i + 1) % NICKNAME_PLACEHOLDERS.length),
      3000,
    );
    return () => clearInterval(t);
  }, []);

  // Declare state
  const [declareType, setDeclareType] = useState("");
  const [insurer, setInsurer] = useState("");
  const [insurerSearch, setInsurerSearch] = useState("");
  const [sumInsured, setSumInsured] = useState(500000);
  const [premium, setPremium] = useState(15000);
  const [declared, setDeclared] = useState([]);

  // Total policies the user will have after this session: prior + uploaded
  // this session + declared this session. Drives whether the nickname
  // input is required (>= 1 → required); first-ever upload stays optional.
  const nicknameRequired =
    existingPolicyCount + parsedPolicies.length + declared.length >= 1;

  const handleFiles = async (files) => {
    const trimmedNick = nickname.trim();
    if (nicknameRequired && !trimmedNick) {
      toast.error("Add a nickname so you can tell this policy apart from your others.");
      fileInputRef.current?.focus?.();
      return;
    }
    const list = Array.from(files);
    setUploading((prev) => [...prev, ...list.map((f) => ({ name: f.name }))]);
    for (const f of list) {
      const fd = new FormData();
      fd.append("file", f);
      if (trimmedNick) fd.append("nickname", trimmedNick);
      try {
        const r = await api.post("/policies/upload", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const pol = r.data?.data?.policy;
        if (pol) setParsedPolicies((prev) => [...prev, pol]);
      } catch (e) {
        const detail = e?.response?.data?.detail;
        if (detail?.error === "nickname_required") {
          toast.error(detail.message || "Please add a nickname before uploading.");
        } else if (detail?.error === "nickname_too_long") {
          toast.error(detail.message || `Nickname must be ${NICKNAME_MAX_LEN} chars or less.`);
        } else if (detail?.error === "not_insurance_document") {
          // Preflight rejected — surface the type hint so the user
          // knows what we think they uploaded ("Looks like a resume…").
          const hint = detail.detected_type_hint;
          const friendly = {
            resume: "Looks like a resume",
            bank_statement: "Looks like a bank statement",
            salary_slip: "Looks like a salary slip",
            invoice: "Looks like an invoice",
            loan_agreement: "Looks like a loan agreement",
            tax_document: "Looks like a tax document",
            lease: "Looks like a lease/rental agreement",
          }[hint];
          if (friendly) {
            toast.error(`${friendly} — we need your policy schedule instead.`);
          } else {
            toast.error(
              `We couldn't recognize ${f.name} as an insurance document. ` +
                "Try your policy schedule from your insurer's email.",
            );
          }
        } else if (detail?.error === "encrypted_pdf") {
          toast.error(
            "This PDF is password-protected. Please remove the password " +
              "and try again, or copy the text into a new PDF.",
          );
        } else if (
          detail?.error === "pdf_too_many_pages" ||
          detail?.error === "pdf_too_few_pages"
        ) {
          const n = detail.page_count;
          toast.error(
            `This PDF is ${n} pages. Insurance documents are usually ` +
              "1-80 pages. Make sure you uploaded the right file.",
          );
        } else if (detail?.error === "invalid_pdf" || detail?.error === "pdf_too_small") {
          toast.error(
            "We couldn't open this as a valid PDF. " +
              "Try re-downloading it from your insurer's email.",
          );
        } else {
          toast.error(`Couldn't parse ${f.name} — try Quick declare instead.`);
        }
      } finally {
        setUploading((prev) => prev.filter((u) => u.name !== f.name));
      }
    }
    // Clear the nickname after a successful upload so the next file
    // gets a fresh field — keeps multi-policy households fast.
    setNickname("");
  };

  const onDrop = (e) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const submitDeclaration = async () => {
    if (!declareType || !insurer || !sumInsured || !premium) {
      toast.error("Fill all fields.");
      return;
    }
    try {
      const r = await api.post("/policies/declare", {
        type: declareType,
        insurer,
        sum_insured: sumInsured,
        premium,
      });
      const pol = r.data?.data?.policy;
      if (pol) setDeclared((prev) => [...prev, pol]);
      setDeclareType("");
      setInsurer("");
      setInsurerSearch("");
      toast.success("Added");
    } catch (e) {
      toast.error("Couldn't save");
    }
  };

  const handleContinue = async () => {
    setSubmitting(true);
    try {
      navigate("/audit/lifestyle");
    } finally {
      setSubmitting(false);
    }
  };

  const insurerList = declareType === "term" ? TERM_INSURERS : HEALTH_INSURERS;
  const filteredInsurers = insurerList.filter((i) =>
    i.toLowerCase().includes(insurerSearch.toLowerCase()),
  );

  const canContinue =
    path === "skip" ||
    (path === "upload" && (parsedPolicies.length > 0 || uploading.length === 0)) ||
    (path === "declare" && declared.length > 0);

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <Header />
      <ProgressBar stage={4} />
      <main className="pt-32 pb-40 md:pb-24 px-6 max-w-2xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
            Step 4 of 6 · 30 seconds
          </p>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-[#0B2545] leading-tight">
            Show us what you already have.
          </h1>
          <p className="mt-2 text-[#475569]">Or skip — we'll work without it.</p>
        </motion.div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <PathCard
            active={path === "upload"}
            badge="Recommended"
            icon={UploadCloud}
            title="Upload policy PDF"
            body="We'll parse sub-limits, exclusions, waiting periods automatically."
            onClick={() => setPath("upload")}
            testId="path-upload"
          />
          <PathCard
            active={path === "declare"}
            icon={PencilLine}
            title="Quick declaration"
            body="Tell us insurer + sum + premium. We'll do the rest."
            onClick={() => setPath("declare")}
            testId="path-declare"
          />
          <PathCard
            active={path === "skip"}
            icon={SkipForward}
            title="Skip for now"
            body="Profile-only audit. Add policies later."
            onClick={() => setPath("skip")}
            testId="path-skip"
          />
        </div>

        <AnimatePresence mode="wait">
          {path === "upload" && (
            <motion.section
              key="upload-block"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className="mt-8"
              data-testid="upload-block"
            >
              {/* Nickname input — required when user has 2+ policies so
                  the dashboard can tell them apart. First upload optional. */}
              <div className="mb-5" data-testid="nickname-block">
                <label
                  htmlFor="nickname-input"
                  className="block text-sm font-semibold text-[#0B2545] mb-1.5"
                >
                  Give this policy a nickname
                  {nicknameRequired && (
                    <span
                      className="text-[#B22222] ml-1"
                      aria-label="required"
                      data-testid="nickname-required-marker"
                    >
                      *
                    </span>
                  )}
                </label>
                <input
                  id="nickname-input"
                  data-testid="nickname-input"
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value.slice(0, NICKNAME_MAX_LEN))}
                  maxLength={NICKNAME_MAX_LEN}
                  placeholder={NICKNAME_PLACEHOLDERS[nicknamePlaceholderIdx]}
                  className="w-full h-12 px-4 rounded-xl border border-[#E1E5EB] bg-white text-[#0B2545] placeholder:text-[#475569]/50 focus:outline-none focus:border-[#13A8A8] focus:ring-2 focus:ring-[#13A8A8]/20 transition-colors"
                />
                <p className="text-xs text-[#475569] mt-1.5">
                  Helps you tell policies apart in your dashboard
                  {nickname.length > 0 && (
                    <span className="ml-2 text-[#475569]/70">
                      · {nickname.length}/{NICKNAME_MAX_LEN}
                    </span>
                  )}
                </p>
              </div>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={onDrop}
                onClick={() => fileInputRef.current?.click()}
                className="cursor-pointer p-10 rounded-xl border-2 border-dashed border-[#13A8A8]/40 bg-[#13A8A8]/[0.04] text-center hover:bg-[#13A8A8]/[0.08] transition-colors"
              >
                <FileText className="w-10 h-10 text-[#13A8A8] mx-auto mb-3" strokeWidth={1.5} />
                <p className="font-semibold text-[#0B2545]">Drop your policy PDFs here</p>
                <p className="text-sm text-[#475569] mt-1">or tap to choose · multiple files OK</p>
                <input
                  ref={fileInputRef}
                  data-testid="file-input"
                  type="file"
                  accept="application/pdf"
                  multiple
                  className="hidden"
                  onChange={(e) => handleFiles(e.target.files)}
                />
              </div>

              {(uploading.length > 0 || parsedPolicies.length > 0) && (
                <div className="mt-5 space-y-3">
                  {uploading.map((u, i) => (
                    <ParsingFile key={i} file={u} />
                  ))}
                  {parsedPolicies.map((p) => (
                    <ParsedPolicyCard key={p.id} policy={p} />
                  ))}
                </div>
              )}
            </motion.section>
          )}

          {path === "declare" && (
            <motion.section
              key="declare-block"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className="mt-8 p-6 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card space-y-5"
              data-testid="declare-block"
            >
              <div>
                <label className="text-sm font-semibold text-[#0B2545] mb-2 block">Type</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { v: "health", l: "Health" },
                    { v: "term", l: "Term life" },
                    { v: "endowment", l: "Endowment / ULIP" },
                    { v: "motor", l: "Motor" },
                    { v: "travel", l: "Travel" },
                  ].map((t) => (
                    <button
                      key={t.v}
                      type="button"
                      data-testid={`declare-type-${t.v}`}
                      onClick={() => {
                        setDeclareType(t.v);
                        setInsurer("");
                      }}
                      className={`px-3.5 py-2 rounded-lg text-sm font-medium border transition-colors ${
                        declareType === t.v
                          ? "bg-[#0B2545] text-white border-[#0B2545]"
                          : "bg-white text-[#475569] border-[#E1E5EB] hover:border-[#13A8A8]/40"
                      }`}
                    >
                      {t.l}
                    </button>
                  ))}
                </div>
              </div>

              {declareType && (
                <>
                  <div>
                    <label className="text-sm font-semibold text-[#0B2545] mb-2 block">
                      Insurer
                    </label>
                    <input
                      data-testid="declare-insurer-input"
                      placeholder="Search insurer"
                      value={insurer || insurerSearch}
                      onChange={(e) => {
                        setInsurer("");
                        setInsurerSearch(e.target.value);
                      }}
                      className="w-full h-11 px-4 rounded-lg border border-[#E1E5EB] bg-white text-sm focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:outline-none"
                    />
                    {insurerSearch && !insurer && (
                      <div className="mt-2 flex flex-wrap gap-2 max-h-40 overflow-auto">
                        {filteredInsurers.slice(0, 8).map((i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => {
                              setInsurer(i);
                              setInsurerSearch("");
                            }}
                            className="px-3 py-1.5 rounded-md bg-[#F8FAFC] text-sm border border-[#E1E5EB] hover:border-[#13A8A8]/40"
                          >
                            {i}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <KvSlider
                    testId="declare-sum-slider"
                    label="Sum insured"
                    value={sumInsured}
                    onChange={setSumInsured}
                    min={200000}
                    max={50000000}
                    step={100000}
                    formatValue={(v) => formatINR(v, { short: true })}
                  />
                  <KvSlider
                    testId="declare-premium-slider"
                    label="Annual premium"
                    value={premium}
                    onChange={setPremium}
                    min={2000}
                    max={500000}
                    step={500}
                    formatValue={(v) => formatINR(v)}
                  />
                  <button
                    data-testid="declare-add"
                    onClick={submitDeclaration}
                    className="w-full h-12 rounded-xl bg-[#13A8A8] hover:bg-[#13A8A8]/90 text-white font-semibold"
                  >
                    Add this policy
                  </button>
                </>
              )}

              {declared.length > 0 && (
                <div className="space-y-2 pt-4 border-t border-[#E1E5EB]">
                  <p className="text-xs font-bold uppercase tracking-[0.15em] text-[#0F7B4F]">
                    Added ({declared.length})
                  </p>
                  {declared.map((d) => (
                    <div
                      key={d.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-[#F8FAFC] text-sm"
                      data-testid={`declared-${d.id}`}
                    >
                      <span className="font-semibold text-[#0B2545]">
                        {d.insurer} · {d.type}
                      </span>
                      <span className="text-[#475569] inline-flex items-center gap-1">
                        <IndianRupee className="w-3.5 h-3.5" />
                        {formatINR(d.premium).replace("₹", "")}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </motion.section>
          )}

          {path === "skip" && (
            <motion.section
              key="skip-block"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className="mt-8 p-6 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card text-center"
              data-testid="skip-block"
            >
              <p className="text-[#475569]">
                We'll generate an audit based on your profile alone. You can add policies anytime
                from the dashboard.
              </p>
            </motion.section>
          )}
        </AnimatePresence>
      </main>

      <BottomCTA
        testId="stage4-continue"
        onClick={handleContinue}
        disabled={!canContinue || uploading.length > 0}
        loading={submitting}
      >
        See my audit →
      </BottomCTA>
    </div>
  );
}
