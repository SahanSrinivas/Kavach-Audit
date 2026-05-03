import React from "react";
import { Button } from "./ui/button";

// Bottom-anchored CTA on mobile, inline on desktop.
export default function BottomCTA({ onClick, disabled, children, testId = "bottom-cta", loading = false }) {
  return (
    <div className="fixed bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC] to-transparent z-30 md:static md:bg-transparent md:p-0 md:mt-10 kv-safe-bottom md:pb-0">
      <Button
        data-testid={testId}
        onClick={onClick}
        disabled={disabled || loading}
        className="w-full md:w-auto md:min-w-[220px] h-14 md:h-12 rounded-xl text-base font-semibold bg-[#0B2545] hover:bg-[#0B2545]/90 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? (
          <span className="inline-flex items-center gap-2">
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Please wait…
          </span>
        ) : (
          children
        )}
      </Button>
    </div>
  );
}
