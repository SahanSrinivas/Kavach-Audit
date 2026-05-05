import React, { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import Header from "../components/Header";

const SCHEDULE_STORAGE_KEY = "kavachly_life_schedule_v1";

function formatInr(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(Number(n));
  } catch {
    return String(n);
  }
}

export default function LifeSchedule() {
  const navigate = useNavigate();
  const raw = useMemo(() => {
    try {
      const s = sessionStorage.getItem(SCHEDULE_STORAGE_KEY);
      return s ? JSON.parse(s) : null;
    } catch {
      return null;
    }
  }, []);

  const schedule = raw?.lifeSchedule;
  const confidence = raw?.confidence || {};
  const warnings = raw?.warnings || [];
  const meta = raw?.meta || {};

  if (!schedule) {
    return (
      <div className="min-h-[100dvh] flex flex-col bg-[#F8FAFC]">
        <Header />
        <main className="flex-1 max-w-lg mx-auto px-6 pt-28 pb-16 text-center">
          <h1 className="font-heading text-2xl font-bold text-[#0B2545]">No Life Schedule yet</h1>
          <p className="mt-3 text-sm text-[#64748B]">Upload your CIS and bond from the life audit step first.</p>
          <Link
            to="/audit/life/start"
            className="mt-8 inline-flex h-11 items-center rounded-xl bg-[#0B2545] px-6 text-sm font-semibold text-white"
          >
            Go to life audit
          </Link>
        </main>
      </div>
    );
  }

  const rows = [
    { label: "Product / plan", value: schedule.productName || "—" },
    { label: "Sum assured", value: formatInr(schedule.sumAssuredInr) },
    { label: "Policy term", value: schedule.policyTermYears != null ? `${schedule.policyTermYears} years` : "—" },
    {
      label: "Premium payment term",
      value: schedule.premiumPaymentTermYears != null ? `${schedule.premiumPaymentTermYears} years` : "—",
    },
    { label: "Modal premium (est.)", value: formatInr(schedule.modalPremiumInr) },
    { label: "Premium frequency", value: schedule.premiumFrequency || "—" },
    { label: "Free-look (days)", value: schedule.freeLookDays != null ? String(schedule.freeLookDays) : "—" },
    {
      label: "Nominee section",
      value: schedule.nomineeSectionLikely ? "Likely present in text" : "Not detected",
    },
  ];

  return (
    <div className="min-h-[100dvh] flex flex-col bg-gradient-to-br from-[#0B2545]/[0.04] via-[#F8FAFC] to-[#13A8A8]/[0.06]">
      <Header />
      <main className="flex-1 w-full max-w-2xl mx-auto px-6 pt-24 pb-16">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#13A8A8]">Life Schedule</p>
        <h1 className="mt-2 font-heading text-3xl font-black text-[#0B2545]">Extracted from your documents</h1>
        <p className="mt-2 text-sm text-[#64748B]">
          Heuristic parse — verify against your CIS and bond. Overall confidence:{" "}
          <span className="font-semibold text-[#0B2545]">{confidence.overall ?? "—"}</span>
        </p>

        {meta.extractedAt ? (
          <p className="mt-1 text-xs text-[#94A3B8]">Extracted at {new Date(meta.extractedAt).toLocaleString()}</p>
        ) : null}

        <div className="mt-8 rounded-2xl border border-[#E1E5EB] bg-white shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {rows.map((r) => (
                <tr key={r.label} className="border-b border-[#E1E5EB] last:border-0">
                  <th className="text-left font-medium text-[#64748B] px-4 py-3 w-[45%] align-top">{r.label}</th>
                  <td className="text-[#0B2545] font-medium px-4 py-3">{r.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {warnings.length > 0 ? (
          <div className="mt-6 rounded-xl border border-[#B45309]/30 bg-[#FFFBEB] px-4 py-3 text-sm text-[#92400E]">
            <p className="font-semibold">Warnings</p>
            <ul className="mt-2 list-disc pl-5 space-y-1">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="mt-10 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => navigate("/audit/life/start")}
            className="inline-flex h-11 items-center rounded-xl border border-[#E1E5EB] bg-white px-5 text-sm font-semibold text-[#0B2545]"
          >
            Upload different PDFs
          </button>
          <Link to="/" className="inline-flex h-11 items-center rounded-xl bg-[#0B2545] px-5 text-sm font-semibold text-white">
            Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
