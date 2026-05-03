import React from "react";

// Sticky 6-dot progress bar for stages 1-6
// stage: 1..6 (current). Dots before = completed, current = active, after = inactive.
export default function ProgressBar({ stage = 1 }) {
  const dots = [1, 2, 3, 4, 5, 6];
  return (
    <div
      data-testid="audit-progress-bar"
      className="fixed top-14 inset-x-0 z-40 flex items-center justify-center gap-3 py-4 bg-[#F8FAFC]/90 backdrop-blur-md border-b border-[#E1E5EB]/60"
    >
      {dots.map((d) => {
        const state = d < stage ? "completed" : d === stage ? "active" : "inactive";
        const cls =
          state === "completed"
            ? "bg-[#13A8A8] w-2.5 h-2.5"
            : state === "active"
              ? "bg-[#0B2545] w-8 h-2.5"
              : "bg-[#E1E5EB] w-2.5 h-2.5";
        return (
          <span
            key={d}
            data-testid={`progress-dot-${d}`}
            className={`rounded-full transition-all duration-300 ${cls}`}
          />
        );
      })}
    </div>
  );
}
