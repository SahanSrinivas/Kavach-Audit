import React from "react";
import { motion } from "framer-motion";
import { ChevronRight, HeartPulse, ScrollText } from "lucide-react";
import SectionError from "./SectionError";

const RIDER_LABELS = {
  critical_illness: "Critical illness",
  personal_accident: "Personal accident",
  hospital_daily_cash: "Hospital daily cash",
  waiver_of_premium: "Waiver of premium",
};

function fmtConf(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return `${Math.round(Number(v) * 100)}%`;
}

/**
 * Saved life schedules + education-only overlap hints vs health policies.
 */
export default function LifePortfolioCard({
  schedules = [],
  overlap = null,
  onOpenSchedule,
  onStartLifeAudit,
  error = null,
  overlapError = null,
  retrying = false,
  overlapRetrying = false,
  onRetry,
  onRetryOverlap,
}) {
  if (error) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        data-testid="dashboard-life-portfolio"
      >
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-4">Life portfolio</p>
        <SectionError
          testId="life-portfolio-error"
          message="Couldn't load life schedules."
          retrying={retrying}
          onRetry={onRetry}
        />
      </motion.section>
    );
  }

  const hints = overlap?.hints ?? [];
  const riders = overlap?.lifeDetectedRiders ?? [];
  const overlapLastRefreshed = overlap?.lastRefreshedAt;
  const showOverlapBody = !overlapError && (hints.length > 0 || riders.length > 0);

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.12 }}
      data-testid="dashboard-life-portfolio"
    >
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Life portfolio</p>
          <h2 className="mt-1 font-heading text-xl font-bold text-[#0B2545]">
            {schedules.length === 0 ? "No saved schedules yet" : `${schedules.length} saved schedule${schedules.length === 1 ? "" : "s"}`}
          </h2>
        </div>
        <button
          type="button"
          onClick={onStartLifeAudit}
          className="inline-flex h-10 items-center justify-center rounded-xl bg-[#0B2545] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#0B2545]/90"
        >
          Life audit
        </button>
      </div>

      {schedules.length > 0 ? (
        <ul className="space-y-2 mb-6">
          {schedules.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onOpenSchedule?.(s.id)}
                className="w-full flex items-center justify-between gap-3 rounded-xl border border-[#E1E5EB] bg-white px-4 py-3 text-left shadow-sm hover:border-[#13A8A8]/40 transition-colors"
              >
                <div className="min-w-0 flex items-center gap-2">
                  <ScrollText className="w-5 h-5 shrink-0 text-[#13A8A8]" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="font-semibold text-[#0B2545] truncate">
                      {(s.meta?.cisFilename && s.meta?.bondFilename
                        ? `${s.meta.cisFilename} + ${s.meta.bondFilename}`
                        : "Life schedule") || "Life schedule"}
                    </p>
                    <p className="text-xs text-[#64748B] mt-0.5">
                      {s.createdAt ? new Date(s.createdAt).toLocaleString() : ""}
                      {s.overallConfidence != null ? ` · Confidence ${fmtConf(s.overallConfidence)}` : ""}
                    </p>
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 shrink-0 text-[#94A3B8]" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-[#64748B] mb-6">
          Run the life audit and save your extracted schedule to see it here and unlock health overlap hints.
        </p>
      )}

      {overlapError ? (
        <div className="mt-4">
          <SectionError
            testId="life-overlap-error"
            message="Couldn't load health overlap hints."
            retrying={overlapRetrying}
            onRetry={onRetryOverlap}
          />
        </div>
      ) : showOverlapBody ? (
        <div className="rounded-2xl border border-[#E1E5EB] bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <HeartPulse className="w-5 h-5 text-[#13A8A8]" aria-hidden="true" />
            <h3 className="font-heading text-sm font-bold text-[#0B2545]">Health overlap hints</h3>
          </div>
          <p className="text-xs text-[#64748B] mb-3 leading-relaxed">
            Education only — not advice. We compare rider keywords from your life documents with wording we can see in your uploaded health policies.
          </p>
          {overlapLastRefreshed ? (
            <p className="text-[11px] text-[#94A3B8] mb-2">
              Last refreshed: {new Date(overlapLastRefreshed).toLocaleString()}
            </p>
          ) : null}
          {riders.length > 0 ? (
            <div className="mb-3">
              <p className="text-xs font-semibold text-[#0B2545] mb-1">Life riders detected</p>
              <ul className="flex flex-wrap gap-2">
                {riders.map((r) => (
                  <li
                    key={r}
                    title="Detected via keyword matching in your uploaded life PDFs."
                    className="rounded-full border border-[#E1E5EB] bg-[#F8FAFC] px-2.5 py-0.5 text-[11px] text-[#475569]"
                  >
                    {RIDER_LABELS[r] || r.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {hints.length > 0 ? (
            <ul className="space-y-3">
              {hints.map((h) => (
                <li key={h.code} className="rounded-lg bg-[#F8FAFC] px-3 py-2.5 border border-[#E1E5EB]/80">
                  <p className="text-sm font-semibold text-[#0B2545]">{h.title}</p>
                  <p className="text-xs text-[#64748B] mt-1 leading-relaxed">{h.detail}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[#64748B]">No specific overlaps flagged — add health policies in the health audit for a fuller picture.</p>
          )}
        </div>
      ) : null}
    </motion.section>
  );
}
