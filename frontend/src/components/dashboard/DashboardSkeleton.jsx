import React from "react";

// Layout-shaped placeholder for the initial dashboard load. Mimics the
// portfolio view's vertical rhythm so users can start parsing the page
// structure before data arrives — better than the centered spinner
// it replaces (which gave no preview of what's coming).
//
// One animate-pulse on the wrapper covers all blocks. No new deps.
//
// Below-the-fold sections (alerts, quick actions) deliberately have no
// skeleton — diminishing returns since the user hasn't scrolled there
// yet on first paint, and the data lands fast enough to fill them
// before the user reaches them.

const Block = ({ className = "" }) => (
  <div className={`bg-[#E1E5EB] rounded-md ${className}`} />
);

function HeroSkeleton() {
  return (
    <div className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card">
      <Block className="h-3 w-24" />
      <div className="mt-4 flex items-center gap-5">
        <div className="w-[140px] h-[140px] rounded-full bg-[#E1E5EB] flex-none" />
        <div className="flex-1 space-y-3">
          <Block className="h-5 w-3/4" />
          <Block className="h-3 w-full" />
          <Block className="h-3 w-5/6" />
        </div>
      </div>
    </div>
  );
}

function ScoreTilesSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="p-4 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card"
        >
          <Block className="h-3 w-16" />
          <Block className="mt-2 h-8 w-12" />
          <Block className="mt-2 h-2 w-20" />
        </div>
      ))}
    </div>
  );
}

function FindingSkeleton() {
  return (
    <div className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-lg bg-[#E1E5EB] flex-none" />
        <div className="flex-1 space-y-2.5">
          <Block className="h-3 w-24" />
          <Block className="h-4 w-full" />
          <Block className="h-4 w-4/5" />
          <Block className="mt-3 h-9 w-28" />
        </div>
      </div>
    </div>
  );
}

function CoverageBarsSkeleton({ rows = 5 }) {
  return (
    <div className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card">
      <Block className="h-3 w-32" />
      <Block className="mt-2 h-5 w-48" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i}>
            <div className="flex justify-between">
              <Block className="h-3 w-20" />
              <Block className="h-3 w-24" />
            </div>
            <Block className="mt-1.5 h-2 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

function PoliciesSkeleton({ count = 3 }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="space-y-2">
          <Block className="h-3 w-24" />
          <Block className="h-5 w-20" />
        </div>
        <Block className="h-10 w-20 rounded-lg" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: count }, (_, i) => (
          <div
            key={i}
            className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card flex items-start gap-4"
          >
            <div className="w-12 h-12 rounded-lg bg-[#E1E5EB] flex-none" />
            <div className="flex-1 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Block className="h-4 w-32" />
                <Block className="h-5 w-20 rounded-md" />
              </div>
              <Block className="h-3 w-3/4" />
              <Block className="h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardSkeleton() {
  return (
    <div
      className="space-y-8 animate-pulse"
      data-testid="dashboard-skeleton"
      aria-busy="true"
      aria-label="Loading dashboard"
    >
      <HeroSkeleton />
      <ScoreTilesSkeleton />
      <FindingSkeleton />
      <CoverageBarsSkeleton />
      <PoliciesSkeleton />
    </div>
  );
}
