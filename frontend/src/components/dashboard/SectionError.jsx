import React from "react";
import { AlertTriangle } from "lucide-react";

// Inline error block for a single dashboard section that failed to load
// while the rest of the dashboard succeeded. Kept compact and contained
// — never blanks the page.
//
// Used by PoliciesList and AlertsInbox today; the top-level audit-failed
// state has its own fuller treatment in DashboardErrorState.
export default function SectionError({ message, retrying = false, onRetry, testId }) {
  return (
    <div
      data-testid={testId}
      className="p-5 rounded-xl bg-white border border-[#B22222]/20 flex items-start gap-3"
    >
      <span className="w-9 h-9 rounded-lg bg-[#B22222]/10 text-[#B22222] flex items-center justify-center flex-none">
        <AlertTriangle className="w-4 h-4" />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#0B2545]">{message}</p>
        {onRetry && (
          <button
            type="button"
            data-testid={testId ? `${testId}-retry` : undefined}
            onClick={onRetry}
            disabled={retrying}
            className="mt-2 text-sm font-semibold text-[#13A8A8] hover:text-[#0F8888] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {retrying ? "Retrying…" : "Retry"}
          </button>
        )}
      </div>
    </div>
  );
}
