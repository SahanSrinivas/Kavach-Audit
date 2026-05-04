import React from "react";
import { motion } from "framer-motion";
import { Bell, AlertTriangle, Info, RefreshCw, Sparkles } from "lucide-react";
import SectionError from "./SectionError";

const ALERT_ICON = {
  renewal: RefreshCw,
  life_event: Info,
  reaudit: Sparkles,
};
const ALERT_COLOR = {
  amber: "text-[#D97706] bg-[#D97706]/10",
  red: "text-[#B22222] bg-[#B22222]/10",
  info: "text-[#13A8A8] bg-[#13A8A8]/10",
};

// Zone D — clickable alert cards.
// onAlertClick receives the full alert; caller decides routing
// (alerts with no target_url are no-ops).
//
// error/onRetry: same independent-failure pattern as PoliciesList.
// /alerts is the lowest-stakes of the three fetches — the user can
// still use the dashboard if it's down — so we just inline a
// SectionError instead of bailing the whole page.
export default function AlertsInbox({
  alerts,
  onAlertClick,
  error = null,
  retrying = false,
  onRetry,
}) {
  if (error) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        data-testid="dashboard-alerts"
      >
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-4 h-4 text-[#13A8A8]" />
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">
            Inbox
          </p>
        </div>
        <SectionError
          testId="alerts-error"
          message="Couldn't load your alerts."
          retrying={retrying}
          onRetry={onRetry}
        />
      </motion.section>
    );
  }
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      data-testid="dashboard-alerts"
    >
      <div className="flex items-center gap-2 mb-4">
        <Bell className="w-4 h-4 text-[#13A8A8]" />
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Inbox</p>
      </div>
      <div className="space-y-3">
        {alerts.map((a) => {
          const Icon = ALERT_ICON[a.type] || AlertTriangle;
          const color = ALERT_COLOR[a.severity] || ALERT_COLOR.info;
          return (
            <button
              key={a.id}
              data-testid={`alert-${a.type}`}
              onClick={() => onAlertClick(a)}
              className="w-full text-left p-5 rounded-xl bg-white border border-[#E1E5EB] hover:border-[#13A8A8]/40 transition-colors flex items-start gap-4"
            >
              <span className={`w-10 h-10 rounded-lg flex items-center justify-center flex-none ${color}`}>
                <Icon className="w-5 h-5" />
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-[#0B2545] leading-snug">{a.headline}</p>
                <p className="mt-1 text-sm text-[#475569]">{a.body}</p>
                <p className="mt-2 text-xs font-semibold text-[#13A8A8]">{a.cta_label} →</p>
              </div>
            </button>
          );
        })}
      </div>
    </motion.section>
  );
}
