import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import FieldConfidenceBadge from "@/components/shared/FieldConfidenceBadge";
import { useAuth } from "@/lib/auth";
import api from "@/lib/api";

const SCHEDULE_STORAGE_KEY = "kavachly_life_schedule_v1";

const RIDER_LABELS = {
  critical_illness: "Critical illness",
  personal_accident: "Personal accident",
  hospital_daily_cash: "Hospital daily cash",
  waiver_of_premium: "Waiver of premium",
};

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
  const [searchParams] = useSearchParams();
  const scheduleId = searchParams.get("id");
  const { user, loading: authLoading } = useAuth();
  const [remote, setRemote] = useState(null);
  const [remoteError, setRemoteError] = useState(null);
  const [remoteLoading, setRemoteLoading] = useState(false);

  useEffect(() => {
    if (!scheduleId || !user) {
      setRemoteLoading(false);
      return undefined;
    }
    let cancelled = false;
    setRemoteError(null);
    setRemoteLoading(true);
    (async () => {
      try {
        const res = await api.get(`/life/schedules/${scheduleId}`);
        if (!cancelled && res.data?.success) setRemote(res.data.data);
      } catch {
        if (!cancelled) setRemoteError("Could not load your saved schedule.");
      } finally {
        if (!cancelled) setRemoteLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scheduleId, user]);

  const raw = useMemo(() => {
    if (remote) {
      return {
        lifeSchedule: remote.lifeSchedule,
        confidence: remote.confidence || {},
        warnings: remote.warnings || [],
        meta: remote.meta || {},
        fieldConfidenceUi: remote.fieldConfidenceUi || [],
      };
    }
    try {
      const s = sessionStorage.getItem(SCHEDULE_STORAGE_KEY);
      return s ? JSON.parse(s) : null;
    } catch {
      return null;
    }
  }, [remote]);

  const schedule = raw?.lifeSchedule;
  const confidence = raw?.confidence || {};
  const warnings = raw?.warnings || [];
  const meta = raw?.meta || {};
  const uiByKey = useMemo(() => {
    const fieldUiList = raw?.fieldConfidenceUi || [];
    return Object.fromEntries(fieldUiList.map((x) => [x.fieldKey, x]));
  }, [raw]);

  if (scheduleId && !authLoading && !user) {
    return (
      <div className="min-h-[100dvh] flex flex-col bg-[#F8FAFC]">
        <Header />
        <main className="flex-1 max-w-lg mx-auto px-6 pt-28 pb-16 text-center">
          <h1 className="font-heading text-2xl font-bold text-[#0B2545]">Sign in to view this schedule</h1>
          <p className="mt-3 text-sm text-[#64748B]">Saved schedules are tied to your Kavachly account.</p>
          <Link to="/login" className="mt-8 inline-flex h-11 items-center rounded-xl bg-[#0B2545] px-6 text-sm font-semibold text-white">
            Sign in
          </Link>
        </main>
      </div>
    );
  }

  if (scheduleId && user && remoteError) {
    return (
      <div className="min-h-[100dvh] flex flex-col bg-[#F8FAFC]">
        <Header />
        <main className="flex-1 max-w-lg mx-auto px-6 pt-28 pb-16 text-center">
          <p className="text-[#B22222] text-sm">{remoteError}</p>
          <Link to="/audit/life/start" className="mt-6 inline-block text-[#13A8A8] font-semibold underline">
            Run life audit again
          </Link>
        </main>
      </div>
    );
  }

  if (scheduleId && user && remoteLoading) {
    return (
      <div className="min-h-[100dvh] flex flex-col bg-[#F8FAFC]">
        <Header />
        <main className="flex-1 flex items-center justify-center px-6">
          <p className="text-sm text-[#64748B]">Loading schedule…</p>
        </main>
      </div>
    );
  }

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

  const tableRows = [
    { key: "productName", label: "Product / plan", value: schedule.productName || "—" },
    { key: "sumAssuredInr", label: "Sum assured", value: formatInr(schedule.sumAssuredInr) },
    { key: "policyTermYears", label: "Policy term", value: schedule.policyTermYears != null ? `${schedule.policyTermYears} years` : "—" },
    {
      key: "premiumPaymentTermYears",
      label: "Premium payment term",
      value: schedule.premiumPaymentTermYears != null ? `${schedule.premiumPaymentTermYears} years` : "—",
    },
    { key: "modalPremiumInr", label: "Modal premium (est.)", value: formatInr(schedule.modalPremiumInr) },
    { key: "premiumFrequency", label: "Premium frequency", value: schedule.premiumFrequency || "—" },
    { key: "freeLookDays", label: "Free-look (days)", value: schedule.freeLookDays != null ? String(schedule.freeLookDays) : "—" },
    {
      key: "nomineeSectionLikely",
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
          Heuristic parse — verify against your CIS and bond. Overall model confidence:{" "}
          <span className="font-semibold text-[#0B2545]">{confidence.overall ?? "—"}</span>
        </p>

        <div className="mt-3 rounded-xl border border-[#E1E5EB] bg-white px-4 py-3 text-xs text-[#475569] leading-relaxed">
          <strong className="text-[#0B2545]">Field badges:</strong> Green = stronger pattern match; amber/red = open your PDF and
          confirm. Scores are internal hints, not legal precision.
        </div>

        {meta.extractedAt ? (
          <p className="mt-2 text-xs text-[#94A3B8]">Extracted at {new Date(meta.extractedAt).toLocaleString()}</p>
        ) : null}

        <div className="mt-8 rounded-2xl border border-[#E1E5EB] bg-white shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {tableRows.map((r) => {
                const sc = confidence[r.key];
                const ui = uiByKey[r.key] || {
                  tier: (sc ?? 0) >= 0.55 ? "high" : (sc ?? 0) >= 0.3 ? "medium" : "low",
                  score: typeof sc === "number" ? sc : 0,
                  verifyInPdf: (sc ?? 0) < 0.55,
                };
                const tier = ui.tier || "low";
                return (
                  <tr key={r.key} className="border-b border-[#E1E5EB] last:border-0">
                    <th className="text-left font-medium text-[#64748B] px-4 py-3 w-[38%] align-top">{r.label}</th>
                    <td className="text-[#0B2545] font-medium px-2 py-3 align-top">{r.value}</td>
                    <td className="px-3 py-3 align-top w-[30%]">
                      <FieldConfidenceBadge tier={tier} score={ui.score} verifyInPdf={ui.verifyInPdf} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {Array.isArray(schedule.detectedRiders) && schedule.detectedRiders.length > 0 ? (
          <div className="mt-6 rounded-2xl border border-[#E1E5EB] bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">Riders (keyword signals)</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {schedule.detectedRiders.map((code) => (
                <li
                  key={code}
                  className="rounded-full bg-[#13A8A8]/10 px-3 py-1 text-xs font-medium text-[#0B2545]"
                >
                  {RIDER_LABELS[code] || code.replace(/_/g, " ")}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-[#94A3B8] leading-snug">
              Heuristic scan of CIS/bond text — confirm rider names and terms in your PDFs.
            </p>
          </div>
        ) : null}

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
            onClick={() => navigate("/audit/life/recommendations")}
            className="inline-flex h-11 items-center rounded-xl bg-[#0B2545] px-5 text-sm font-semibold text-white"
          >
            See recommendations
          </button>
          <button
            type="button"
            onClick={() => navigate("/audit/life/start")}
            className="inline-flex h-11 items-center rounded-xl border border-[#E1E5EB] bg-white px-5 text-sm font-semibold text-[#0B2545]"
          >
            Upload different PDFs
          </button>
          <Link to="/" className="inline-flex h-11 items-center rounded-xl border border-[#E1E5EB] bg-white px-5 text-sm font-semibold text-[#0B2545]">
            Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
