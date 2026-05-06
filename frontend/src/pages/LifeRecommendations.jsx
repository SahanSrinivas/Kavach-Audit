import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, ArrowLeft, ChevronRight, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import Header from "../components/Header";
import api from "../lib/api";
import { formatINR } from "../lib/currency";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../components/ui/sheet";

const MOBILE_BREAKPOINT_PX = 768;
const STICKY_COMPACT_SCROLL_Y = 28;

const FINDING_SEVERITY = {
  underinsured_life: "red",
  no_nominee: "red",
  missing_critical_illness: "amber",
  missing_accidental_death: "amber",
  term_too_short: "amber",
  endowment_returns_low: "amber",
  single_dependent_risk: "amber",
};

const HOW_TO_ACT = {
  term_top_up: {
    title: "How to act",
    steps: [
      "Get quotes from 3 top-CSR insurers (HDFC Life, Max Life, ICICI Pru are commonly cited examples - compare current CSR data before choosing).",
      "Choose online term plans for lower premiums.",
      "Disclose all medical history truthfully - non-disclosure can invalidate claims.",
    ],
  },
  set_nominee: {
    title: "How to act",
    steps: [
      "Log in to your insurer customer portal or call customer service.",
      "Submit nominee details, relationship, and ID proof.",
      "Add a contingent nominee for additional safety.",
      "Insurer confirmation usually arrives within 7-10 days.",
    ],
  },
  ci_rider_or_standalone: {
    title: "How to act",
    steps: [
      "Decide rider vs standalone based on your existing term policy.",
      "Riders are usually cheaper but tied to the base policy.",
      "Standalone CI plans are portable across insurers.",
      "Verify covered conditions carefully (fewer conditions generally need scrutiny).",
    ],
  },
  ad_rider: {
    title: "How to act",
    steps: [
      "Add to your existing term policy at renewal (often cheaper than standalone).",
      "Confirm whether payout is additional sum assured or a multiplier of base cover.",
      "Check employer group accidental cover before buying more.",
    ],
  },
  extend_term: {
    title: "How to act",
    steps: [
      "If extension is unavailable, buy a fresh term plan first.",
      "Expect fresh medical underwriting for the new plan.",
      "Do not surrender the existing policy until new issuance is complete.",
    ],
  },
  term_plus_invest: {
    title: "How to act",
    steps: [
      "Plan replacement split: same monthly premium -> term cover + MF SIP.",
      "Use SEBI-registered direct mutual fund schemes where suitable.",
      "For 20+ year horizons, many users consider a 70% equity / 30% debt mix.",
      "Move out of endowment only after new term cover is issued.",
    ],
  },
  diversify_cover: {
    title: "How to act",
    steps: [
      "Add a second smaller policy from a different insurer.",
      "Split total cover across two policies (for example, Rs. 1Cr + Rs. 50L).",
      "Update nominee and contingent nominee on both policies.",
    ],
  },
  stay_with_current: {
    title: "How to act",
    steps: ["No action needed right now."],
    footer:
      "Re-audit at your next life event (marriage, child, home loan, parent dependency change) or at policy renewal.",
  },
};

const MOCK_RECOMMENDATIONS = [
  {
    id: "rec-term_top_up-underinsured_life",
    type: "term_top_up",
    title: "Top up your life cover",
    product_type: "Term Insurance",
    suggested_sum_assured_inr: 2500000,
    suggested_term_years: 25,
    suggested_provider_tier: "top-CSR insurer",
    estimated_annual_premium_range: [4500, 6500],
    reasoning:
      "Your current life cover is below common income-replacement baselines. A top-up term layer can close the gap while preserving your existing policy.",
    triggered_by_finding: "underinsured_life",
    priority_rank: 1,
  },
  {
    id: "rec-ci_rider_or_standalone-missing_critical_illness",
    type: "ci_rider_or_standalone",
    title: "Add critical illness protection",
    product_type: "Critical Illness Rider or Standalone Plan",
    suggested_sum_assured_inr: 600000,
    suggested_term_years: 25,
    suggested_provider_tier: "any IRDAI-registered life insurer",
    estimated_annual_premium_range: [500, 1000],
    reasoning:
      "Critical illness can interrupt income even when hospitalization is covered. A CI layer helps with non-medical recovery costs.",
    triggered_by_finding: "missing_critical_illness",
    priority_rank: 3,
  },
  {
    id: "rec-set_nominee-no_nominee",
    type: "set_nominee",
    title: "Add a nominee to your policy",
    product_type: "Action - not a new product",
    suggested_sum_assured_inr: null,
    suggested_term_years: null,
    suggested_provider_tier: "Existing insurer",
    estimated_annual_premium_range: null,
    reasoning:
      "Nominee details reduce claim friction for dependents and can usually be updated quickly through insurer support channels.",
    triggered_by_finding: "no_nominee",
    priority_rank: 2,
  },
];

function RecommendationsSkeleton() {
  return (
    <div className="space-y-4 animate-pulse" aria-busy="true" aria-label="Loading recommendations">
      {[0, 1, 2].map((item) => (
        <div key={item} className="rounded-2xl border border-[#E1E5EB] bg-white p-5">
          <div className="h-3 w-24 rounded bg-[#E1E5EB]" />
          <div className="mt-3 h-6 w-2/3 rounded bg-[#E1E5EB]" />
          <div className="mt-2 h-4 w-full rounded bg-[#E1E5EB]" />
          <div className="mt-1 h-4 w-4/5 rounded bg-[#E1E5EB]" />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="h-16 rounded-xl bg-[#E1E5EB]" />
            <div className="h-16 rounded-xl bg-[#E1E5EB]" />
          </div>
        </div>
      ))}
    </div>
  );
}

function severityLabel(type) {
  const sev = FINDING_SEVERITY[type] || "info";
  if (sev === "red") return "Critical";
  if (sev === "amber") return "Attention needed";
  return "Info";
}

function severityPillClass(type) {
  const sev = FINDING_SEVERITY[type] || "info";
  if (sev === "red") return "bg-[#B22222]/10 text-[#B22222]";
  if (sev === "amber") return "bg-amber-100 text-amber-800";
  return "bg-[#13A8A8]/10 text-[#0B2545]";
}

function rangeLabel(range) {
  if (!Array.isArray(range) || range.length !== 2) return "Estimated premium: —";
  const [low, high] = range;
  return `Estimated premium: ${formatINR(low)} - ${formatINR(high)} / year`;
}

export default function LifeRecommendations() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const mock = searchParams.get("mock") === "1";
  const [loading, setLoading] = useState(true);
  const [errorType, setErrorType] = useState(null);
  const [recs, setRecs] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [sheetRec, setSheetRec] = useState(null);
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < MOBILE_BREAKPOINT_PX : false
  );
  const [compactHeader, setCompactHeader] = useState(false);

  const fetchRecommendations = async () => {
    setLoading(true);
    setErrorType(null);
    try {
      if (mock) {
        setRecs(MOCK_RECOMMENDATIONS);
        setLoading(false);
        return;
      }
      const response = await api.get("/life/recommendations");
      const payload = response?.data?.data?.recommendations || [];
      setRecs(Array.isArray(payload) ? payload : []);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 404 && detail === "life_audit_not_found") {
        setErrorType("life_audit_not_found");
      } else if (status === 404 && detail === "user_not_found") {
        setErrorType("user_not_found");
      } else {
        setErrorType("network");
        toast.error("Couldn't load recommendations", {
          description: "Please retry in a moment.",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [mock]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT_PX);
    const onScroll = () => setCompactHeader(window.scrollY > STICKY_COMPACT_SCROLL_Y);
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  const sortedRecs = useMemo(
    () =>
      [...recs].sort((a, b) => {
        const aSev = FINDING_SEVERITY[a.triggered_by_finding] || "info";
        const bSev = FINDING_SEVERITY[b.triggered_by_finding] || "info";
        const sevWeight = { red: 0, amber: 1, info: 2 };
        if (sevWeight[aSev] !== sevWeight[bSev]) return sevWeight[aSev] - sevWeight[bSev];
        return (a.priority_rank || 999) - (b.priority_rank || 999);
      }),
    [recs]
  );

  const openHowToAct = (rec) => {
    if (isMobile) {
      setSheetRec(rec);
      return;
    }
    setExpandedId((prev) => (prev === rec.id ? null : rec.id));
  };

  const renderErrorState = () => {
    if (errorType === "life_audit_not_found") {
      return (
        <div className="rounded-2xl border border-[#E1E5EB] bg-white p-6 text-center">
          <h2 className="font-heading text-2xl font-bold text-[#0B2545]">
            We need an audit before recommendations
          </h2>
          <p className="mt-2 text-sm text-[#64748B]">
            Run your life audit first so we can rank next-best actions.
          </p>
          <Link
            to="/audit/life/start"
            className="mt-6 inline-flex h-11 items-center rounded-xl bg-[#0B2545] px-5 text-sm font-semibold text-white"
          >
            Run audit
          </Link>
        </div>
      );
    }
    if (errorType === "user_not_found") {
      return (
        <div className="rounded-2xl border border-[#E1E5EB] bg-white p-6 text-center">
          <h2 className="font-heading text-2xl font-bold text-[#0B2545]">Profile incomplete</h2>
          <p className="mt-2 text-sm text-[#64748B]">
            Complete your profile so recommendations can be matched to your context.
          </p>
          <Link
            to="/audit/start"
            className="mt-6 inline-flex h-11 items-center rounded-xl bg-[#0B2545] px-5 text-sm font-semibold text-white"
          >
            Complete profile
          </Link>
        </div>
      );
    }
    return (
      <div className="rounded-2xl border border-[#B22222]/20 bg-white p-5">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 text-[#B22222]" aria-hidden="true" />
          <div className="flex-1">
            <p className="font-semibold text-[#0B2545]">Could not load recommendations</p>
            <p className="mt-1 text-sm text-[#64748B]">
              Please check your connection and retry.
            </p>
            <button
              type="button"
              onClick={fetchRecommendations}
              className="mt-3 inline-flex h-10 items-center rounded-lg border border-[#E1E5EB] px-4 text-sm font-semibold text-[#0B2545]"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <Header />

      <div className="sticky top-14 z-40 border-b border-[#E1E5EB] bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between px-4 sm:px-6">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-[#0B2545] hover:bg-[#F1F5F9]"
            aria-label="Go back"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-2 overflow-hidden">
            <ShieldCheck className="h-4 w-4 flex-none text-[#13A8A8]" aria-hidden="true" />
            <span
              className={`whitespace-nowrap text-sm font-semibold text-[#0B2545] transition-all ${
                compactHeader ? "max-w-0 opacity-0 md:max-w-xs md:opacity-100" : "max-w-xs opacity-100"
              }`}
            >
              Life recommendations
            </span>
          </div>
          <span className="text-[11px] font-semibold uppercase tracking-wide text-[#13A8A8]">
            Ranked
          </span>
        </div>
      </div>

      <main className="mx-auto w-full max-w-4xl px-4 pb-16 pt-6 sm:px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#13A8A8]">
          Action plan
        </p>
        <h1 className="mt-2 font-heading text-3xl font-black text-[#0B2545]">
          What to do next on your life cover
        </h1>
        <p className="mt-2 text-sm text-[#64748B]">
          Ranked recommendations based on your audit findings. We suggest insurer tiers, not products.
        </p>

        {loading ? <div className="mt-6"><RecommendationsSkeleton /></div> : null}
        {!loading && errorType ? <div className="mt-6">{renderErrorState()}</div> : null}

        {!loading && !errorType && (
          <section className="mt-6 space-y-4" aria-label="Recommendations list">
            {sortedRecs.map((rec) => {
              const guidance = HOW_TO_ACT[rec.type] || HOW_TO_ACT.stay_with_current;
              const expanded = expandedId === rec.id;
              return (
                <article
                  key={rec.id}
                  className="overflow-hidden rounded-2xl border border-[#E1E5EB] bg-white shadow-sm"
                >
                  <div className="p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-[11px] font-bold uppercase tracking-wide ${severityPillClass(
                          rec.triggered_by_finding
                        )}`}
                      >
                        {severityLabel(rec.triggered_by_finding)}
                      </span>
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-[#94A3B8]">
                        Priority {rec.priority_rank}
                      </span>
                    </div>

                    <h2 className="mt-3 font-heading text-2xl font-bold text-[#0B2545]">{rec.title}</h2>
                    <p className="mt-1 text-sm text-[#475569]">{rec.product_type}</p>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div className="rounded-xl bg-[#F8FAFC] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
                          Suggested cover
                        </p>
                        <p className="mt-1 text-base font-semibold text-[#0B2545]">
                          {rec.suggested_sum_assured_inr ? formatINR(rec.suggested_sum_assured_inr) : "N/A"}
                        </p>
                      </div>
                      <div className="rounded-xl bg-[#F8FAFC] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
                          Suggested term
                        </p>
                        <p className="mt-1 text-base font-semibold text-[#0B2545]">
                          {rec.suggested_term_years ? `${rec.suggested_term_years} years` : "N/A"}
                        </p>
                      </div>
                    </div>

                    <p className="mt-3 text-sm font-semibold text-[#0B2545]">
                      {rangeLabel(rec.estimated_annual_premium_range)}
                    </p>
                    <p className="mt-1 text-xs text-[#64748B]">
                      Suggested provider tier: {rec.suggested_provider_tier}
                    </p>

                    <p className="mt-4 text-sm leading-relaxed text-[#475569]">{rec.reasoning}</p>

                    <button
                      type="button"
                      onClick={() => openHowToAct(rec)}
                      className="mt-4 inline-flex h-10 items-center rounded-lg border border-[#D8E1EA] px-4 text-sm font-semibold text-[#0B2545] hover:bg-[#F8FAFC] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8]"
                      aria-expanded={isMobile ? undefined : expanded}
                      aria-label={`How to act on ${rec.title}`}
                    >
                      How to act
                      <ChevronRight className={`ml-1 h-4 w-4 transition-transform ${expanded ? "rotate-90" : ""}`} />
                    </button>

                    {!isMobile && expanded && (
                      <div className="mt-4 rounded-xl border border-[#E1E5EB] bg-[#F8FAFC] p-4">
                        <h3 className="text-sm font-bold text-[#0B2545]">{guidance.title}</h3>
                        <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-[#475569]">
                          {guidance.steps.map((step) => (
                            <li key={step}>{step}</li>
                          ))}
                        </ol>
                        {guidance.footer ? (
                          <p className="mt-3 text-xs font-medium text-[#64748B]">{guidance.footer}</p>
                        ) : null}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </main>

      <Sheet open={!!sheetRec} onOpenChange={(open) => !open && setSheetRec(null)}>
        <SheetContent side="bottom" className="h-[100dvh] max-h-[100dvh] w-full max-w-none rounded-none p-0">
          {sheetRec ? (
            <div className="flex h-full flex-col">
              <SheetHeader className="border-b border-[#E1E5EB] px-4 py-4 text-left">
                <SheetTitle className="text-[#0B2545]">{sheetRec.title}</SheetTitle>
                <SheetDescription>How to act on this recommendation</SheetDescription>
              </SheetHeader>
              <div className="overflow-y-auto px-4 py-4">
                <ol className="list-decimal space-y-3 pl-5 text-sm text-[#475569]">
                  {(HOW_TO_ACT[sheetRec.type] || HOW_TO_ACT.stay_with_current).steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
                {(HOW_TO_ACT[sheetRec.type] || HOW_TO_ACT.stay_with_current).footer ? (
                  <p className="mt-4 text-xs font-medium text-[#64748B]">
                    {(HOW_TO_ACT[sheetRec.type] || HOW_TO_ACT.stay_with_current).footer}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
