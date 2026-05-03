import React from "react";

// Reusable chip — selectable card-style chip used across stages 2/4/5
export default function Chip({ active, onClick, children, testId, fullWidth = true, disabled = false }) {
  const base =
    "px-5 py-3.5 rounded-xl border-2 transition-all cursor-pointer text-center font-medium flex items-center justify-center gap-2";
  const state = active
    ? "border-[#0B2545] bg-[#0B2545]/[0.04] text-[#0B2545] shadow-sm"
    : "border-[#E1E5EB] bg-white text-[#475569] hover:border-[#13A8A8]/40 hover:bg-[#F8FAFC]";
  const dis = disabled ? "opacity-40 cursor-not-allowed" : "";
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={disabled ? undefined : onClick}
      className={`${base} ${state} ${dis} ${fullWidth ? "w-full" : ""}`}
    >
      {children}
    </button>
  );
}
