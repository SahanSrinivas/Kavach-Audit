import React, { useCallback, useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { toast } from "sonner";
import {
  ArrowRight,
  Building2,
  Check,
  FileStack,
  FileText,
  HandCoins,
  HeartHandshake,
  Layers,
  MapPin,
  Scale,
  ScrollText,
  Send,
  Shield,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/lib/utils";

const NAV_SHOW_AFTER_PX = 600;
const LANDING_AUDIT_TAB_KEY = "kavachly_landing_audit_tab";

function readStoredAuditTab() {
  try {
    const v = sessionStorage.getItem(LANDING_AUDIT_TAB_KEY);
    if (v === "health" || v === "life") return v;
  } catch (_) {
    /* ignore */
  }
  return "health";
}

const fadeUp = (reduceMotion) => ({
  initial: reduceMotion ? false : { opacity: 0, y: 16 },
  whileInView: reduceMotion ? undefined : { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-8% 0px" },
  transition: { duration: 0.45, ease: [0.25, 1, 0.5, 1] },
});

function smoothScrollToId(id, prefersReduced) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: prefersReduced ? "auto" : "smooth", block: "start" });
}

/* —— Hero illustration: stylized policy + scan line (SVG) —— */
function HeroIllustration({ className, reduceMotion, auditMode = "health" }) {
  return (
    <div
      className={cn("relative select-none", className)}
      aria-hidden="true"
    >
      <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-white/80 to-white/40 shadow-[0_20px_60px_rgba(11,37,69,0.12)] border border-white/60 backdrop-blur-sm" />
      <svg
        viewBox="0 0 400 320"
        className="relative w-full h-auto max-w-[min(100%,420px)] mx-auto"
        role="img"
        aria-label=""
      >
        <defs>
          <linearGradient id="hero-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0B2545" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#FF6B6B" stopOpacity="0.15" />
          </linearGradient>
          <linearGradient id="scan-grad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#FF6B6B" stopOpacity="0" />
            <stop offset="50%" stopColor="#FF6B6B" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#FF6B6B" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x="48" y="40" width="260" height="220" rx="12" fill="white" stroke="#0B2545" strokeOpacity="0.12" />
        <rect x="64" y="64" width="120" height="10" rx="3" fill="#0B2545" fillOpacity="0.12" />
        <rect x="64" y="84" width="200" height="6" rx="2" fill="#0B2545" fillOpacity="0.08" />
        <rect x="64" y="98" width="180" height="6" rx="2" fill="#0B2545" fillOpacity="0.08" />
        <rect x="64" y="120" width="100" height="6" rx="2" fill="#0B2545" fillOpacity="0.08" />
        <rect x="64" y="150" width="200" height="64" rx="6" fill="url(#hero-grad)" />
        <path
          d="M200 50 L200 250"
          stroke="url(#scan-grad)"
          strokeWidth="36"
          opacity="0.9"
        />
        {reduceMotion ? (
          <g>
            <rect x="40" y="78" width="320" height="3" fill="#13A8A8" fillOpacity="0.35" />
          </g>
        ) : (
          <motion.g
            animate={{ y: [0, 140, 0] }}
            transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
          >
            <rect x="40" y="78" width="320" height="3" fill="#13A8A8" fillOpacity="0.35" />
          </motion.g>
        )}
        <circle cx="300" cy="200" r="28" fill="#0B2545" fillOpacity="0.9" />
        <path
          d="M290 200 L298 208 L315 188"
          stroke="white"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />
        <text x="72" y="210" fontSize="11" fill="#0B2545" fillOpacity="0.5" fontFamily="system-ui">
          {String(auditMode) === "life" ? "Bond · Life" : "Schedule · Health"}
        </text>
      </svg>
    </div>
  );
}

function ProblemIcon({ type, className }) {
  const base = "w-10 h-10 sm:w-12 sm:h-12";
  if (type === "cap")
    return (
      <div className={cn("rounded-2xl bg-[#0B2545]/8 flex items-center justify-center text-[#0B2545]", base, className)}>
        <Layers className="w-5 h-5 sm:w-6 sm:h-6" strokeWidth={2} aria-hidden="true" />
      </div>
    );
  if (type === "commission")
    return (
      <div className={cn("rounded-2xl bg-[#0B2545]/8 flex items-center justify-center text-[#0B2545]", base, className)}>
        <HandCoins className="w-5 h-5 sm:w-6 sm:h-6" strokeWidth={2} aria-hidden="true" />
      </div>
    );
  return (
    <div className={cn("rounded-2xl bg-[#0B2545]/8 flex items-center justify-center text-[#0B2545]", base, className)}>
      <ScrollText className="w-5 h-5 sm:w-6 sm:h-6" strokeWidth={2} aria-hidden="true" />
    </div>
  );
}

function StepVisual({ step, className }) {
  const s = String(step);
  if (s === "1")
    return (
      <div
        className={cn(
          "w-[200px] h-[200px] rounded-3xl flex items-center justify-center bg-gradient-to-b from-white to-[#F1F5F9] border border-[#E1E5EB] shadow-sm",
          className,
        )}
        aria-hidden="true"
      >
        <FileStack className="w-24 h-24 text-[#0B2545] opacity-90" strokeWidth={1.25} />
      </div>
    );
  if (s === "2")
    return (
      <div
        className={cn(
          "w-[200px] h-[200px] rounded-3xl flex items-center justify-center bg-gradient-to-b from-white to-[#F1F5F9] border border-[#E1E5EB] shadow-sm",
          className,
        )}
        aria-hidden="true"
      >
        <Sparkles className="w-24 h-24 text-[#13A8A8]" strokeWidth={1.25} />
      </div>
    );
  return (
    <div
      className={cn(
        "w-[200px] h-[200px] rounded-3xl flex items-center justify-center bg-gradient-to-b from-white to-[#F1F5F9] border border-[#E1E5EB] shadow-sm",
        className,
      )}
      aria-hidden="true"
    >
      <ShieldCheck className="w-24 h-24 text-[#FF6B6B]" strokeWidth={1.25} />
    </div>
  );
}

/** Stylized product preview (static, not live Dashboard embed) */
function DashboardMock() {
  return (
    <div
      className="rounded-2xl border border-[#E1E5EB] bg-white shadow-[0_20px_50px_rgba(11,37,69,0.08)] overflow-hidden"
      data-testid="landing-dashboard-mock"
    >
      <div className="h-2 bg-gradient-to-r from-[#0B2545] via-[#13A8A8] to-[#FF6B6B] opacity-90" />
      <div className="p-5 sm:p-6 space-y-4">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#13A8A8]">Portfolio</p>
        <div className="flex flex-wrap gap-4 items-start">
          <div className="relative w-[120px] h-[120px] shrink-0">
            <svg viewBox="0 0 120 120" className="w-full h-full" aria-hidden="true">
              <circle cx="60" cy="60" r="52" fill="none" stroke="#E1E5EB" strokeWidth="10" />
              <circle
                cx="60"
                cy="60"
                r="52"
                fill="none"
                stroke="#0F7B4F"
                strokeWidth="10"
                strokeDasharray={`${0.72 * 326} 326`}
                strokeLinecap="round"
                transform="rotate(-90 60 60)"
              />
              <text x="60" y="66" textAnchor="middle" fontSize="22" fontWeight="700" fill="#0B2545">
                72
              </text>
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-heading font-bold text-lg text-[#0B2545] leading-tight">Gap score</p>
            <p className="text-sm text-[#475569] mt-1">Where your household cover meets reality.</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:gap-3">
          {["Coverage", "Cost", "Claims", "Gaps"].map((label) => (
            <div
              key={label}
              className="rounded-xl border border-[#E1E5EB] bg-[#F8FAFC] px-3 py-2 text-center"
            >
              <p className="text-xs text-[#64748B]">{label}</p>
              <p className="font-heading font-bold text-[#0B2545]">—</p>
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-[#B22222]/30 bg-[#B22222]/5 p-3">
          <p className="text-xs font-semibold text-[#B22222]">Top finding</p>
          <p className="text-sm text-[#0B2545] mt-0.5">Room rent sub-limit may cap high metro claims.</p>
        </div>
        <div className="rounded-xl border border-[#E1E5EB] p-3 flex items-center justify-between gap-2">
          <div>
            <p className="text-xs text-[#64748B]">Active policy</p>
            <p className="font-medium text-[#0B2545] text-sm">Health · Family floater</p>
          </div>
          <FileText className="w-5 h-5 text-[#13A8A8]" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  const reduceMotion = useReducedMotion();
  const formId = useId();
  const [showStickyNav, setShowStickyNav] = useState(false);
  const [email, setEmail] = useState("");
  const [phoneLocal, setPhoneLocal] = useState("");
  const [auditTab, setAuditTab] = useState(readStoredAuditTab);
  const auditEntryPath = auditTab === "life" ? "/audit/life/start" : "/audit/start";

  useEffect(() => {
    try {
      sessionStorage.setItem(LANDING_AUDIT_TAB_KEY, auditTab);
    } catch (_) {
      /* ignore */
    }
  }, [auditTab]);

  const onScrollNav = useCallback(() => {
    setShowStickyNav(window.scrollY > NAV_SHOW_AFTER_PX);
  }, []);

  useEffect(() => {
    onScrollNav();
    window.addEventListener("scroll", onScrollNav, { passive: true });
    return () => window.removeEventListener("scroll", onScrollNav);
  }, [onScrollNav]);

  const scrollHow = () => smoothScrollToId("how-it-works", reduceMotion);

  const handleBetaSubmit = (e) => {
    e.preventDefault();
    const trimmedEmail = email.trim();
    const digits = phoneLocal.replace(/\D/g, "");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      toast.error("Please enter a valid email.");
      return;
    }
    if (!/^\d{10}$/.test(digits)) {
      toast.error("Enter a valid 10-digit mobile number.");
      return;
    }
    toast.success("You're on the list. We'll text you when your invite is ready.");
    setEmail("");
    setPhoneLocal("");
  };

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC] text-[#0B2545]">
      {/* Ambient background orbs (no rainbow blobs) */}
      <div
        className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
        aria-hidden="true"
      >
        <div
          className="absolute -top-32 -right-24 w-[min(80vw,480px)] h-[min(80vw,480px)] rounded-full bg-[#0B2545]/[0.06] blur-3xl motion-safe:animate-mesh-slow"
        />
        <div
          className="absolute top-1/3 -left-32 w-[min(70vw,400px)] h-[min(70vw,400px)] rounded-full bg-[#FF6B6B]/[0.07] blur-3xl motion-safe:animate-mesh-slow-alt"
        />
      </div>

      {/* Sticky nav: appears after ~600px scroll */}
      <motion.header
        role="navigation"
        aria-label="In-page actions"
        initial={false}
        animate={{
          opacity: showStickyNav ? 1 : 0,
          y: showStickyNav ? 0 : -8,
          pointerEvents: showStickyNav ? "auto" : "none",
        }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="fixed top-0 left-0 right-0 z-50 border-b border-[#E1E5EB]/80 bg-white/95 backdrop-blur-md"
      >
        <div className="max-w-6xl mx-auto h-12 sm:h-14 flex items-center justify-between px-4 sm:px-6">
          <Link
            to="/"
            className="inline-flex items-baseline gap-1.5 group focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2 rounded-md"
            data-testid="landing-sticky-wordmark"
          >
            <ShieldCheck
              className="w-4 h-4 text-[#13A8A8] translate-y-[1px]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
            <span className="font-heading font-bold text-[#0B2545] text-lg sm:text-xl leading-none">
              Kavachly
            </span>
          </Link>
          <Link
            to={auditEntryPath}
            className="inline-flex h-9 sm:h-10 items-center gap-1.5 rounded-lg bg-[#0B2545] px-3 sm:px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#0B2545]/90 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2"
            data-testid="landing-sticky-cta"
          >
            {auditTab === "life" ? "Life audit" : "Health audit"}
            <ArrowRight className="w-4 h-4" strokeWidth={2.5} aria-hidden="true" />
          </Link>
        </div>
      </motion.header>

      {/* Wordmark only — no top nav above the fold */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-5 sm:pt-7">
        <Link
          to="/"
          className="inline-flex items-baseline gap-1.5 w-fit focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2 rounded-md"
          aria-label="Kavachly home"
        >
          <ShieldCheck
            className="w-5 h-5 sm:w-6 sm:h-6 text-[#13A8A8] translate-y-[1px]"
            strokeWidth={2.5}
            aria-hidden="true"
          />
          <span className="font-heading font-bold text-[#0B2545] text-[22px] sm:text-2xl leading-none">
            Kavachly
          </span>
        </Link>
      </div>

      {/* 1 — Hero */}
      <section
        className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 sm:pt-10 pb-16 sm:pb-20"
        aria-labelledby="hero-heading"
      >
        <div className="rounded-3xl bg-gradient-to-br from-[#0B2545] via-[#0d2d56] to-[#123a6e] p-1 shadow-[0_24px_80px_rgba(11,37,69,0.2)]">
          <div className="rounded-[22px] bg-gradient-to-b from-white/95 to-[#F0F4F8] px-5 sm:px-10 lg:px-12 py-10 sm:py-14 lg:py-16">
            <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 lg:gap-12 items-center">
              <div>
                <p className="text-[11px] sm:text-xs font-semibold uppercase tracking-[0.2em] text-[#0B2545]">
                  India&apos;s first honest insurance audit
                </p>
                <div
                  className="mt-4 inline-flex w-full max-w-md rounded-2xl border border-[#0B2545]/12 bg-white/80 p-1 shadow-sm"
                  role="tablist"
                  aria-label="Choose audit type"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={auditTab === "health"}
                    id="landing-audit-tab-health"
                    className={cn(
                      "flex-1 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2",
                      auditTab === "health"
                        ? "bg-[#0B2545] text-white shadow-sm"
                        : "text-[#475569] hover:bg-[#0B2545]/[0.06]",
                    )}
                    onClick={() => setAuditTab("health")}
                  >
                    Health insurance audit
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={auditTab === "life"}
                    id="landing-audit-tab-life"
                    className={cn(
                      "flex-1 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2",
                      auditTab === "life"
                        ? "bg-[#0B2545] text-white shadow-sm"
                        : "text-[#475569] hover:bg-[#0B2545]/[0.06]",
                    )}
                    onClick={() => setAuditTab("life")}
                  >
                    Life insurance audit
                  </button>
                </div>
                <h1
                  id="hero-heading"
                  className="mt-5 font-heading text-4xl sm:text-5xl lg:text-[3.25rem] font-black tracking-tight text-[#0B2545] leading-[1.05]"
                >
                  Insurance, audited.
                </h1>
                <p className="mt-5 text-base sm:text-lg text-[#475569] max-w-xl leading-relaxed">
                  {auditTab === "life"
                    ? "We decode CIS and policy bonds against IRDAI-style insurer signals—commission-neutral, evidence-led."
                    : "We read your policy so you don't have to. Get a structured audit of what you actually have, in 90 seconds."}
                </p>
                <div className="mt-8 flex flex-col sm:flex-row gap-3 sm:gap-4">
                  <Link
                    to={auditEntryPath}
                    className="inline-flex h-12 sm:h-14 w-full sm:w-auto shrink-0 items-center justify-center gap-2 rounded-xl bg-[#0B2545] px-6 sm:px-8 text-base font-semibold text-white shadow-[0_8px_30px_rgb(11,37,69,0.2)] hover:bg-[#0B2545]/90 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2"
                    data-testid="landing-hero-primary-cta"
                  >
                    <span className="whitespace-nowrap">
                      {auditTab === "life" ? "Start life audit" : "Start health audit"}
                    </span>
                    <ArrowRight className="w-5 h-5 shrink-0" strokeWidth={2.5} aria-hidden="true" />
                  </Link>
                  <button
                    type="button"
                    onClick={scrollHow}
                    className="inline-flex h-12 sm:h-14 w-full sm:w-auto items-center justify-center rounded-xl border-2 border-[#0B2545]/15 bg-white px-6 sm:px-8 text-base font-semibold text-[#0B2545] hover:bg-[#0B2545]/[0.04] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2"
                  >
                    How it works
                  </button>
                </div>
              </div>
              <HeroIllustration
                reduceMotion={reduceMotion}
                auditMode={auditTab}
                className="mx-auto lg:mx-0 lg:justify-self-end"
              />
            </div>
          </div>
        </div>
      </section>

      {/* 2 — Trust strip */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-14 sm:pb-16" aria-label="Trust highlights">
        <div className="rounded-2xl bg-white border border-[#E1E5EB] px-4 py-5 sm:px-8 sm:py-6 shadow-sm">
          <ul className="grid grid-cols-2 lg:grid-cols-4 gap-x-4 gap-y-5 lg:gap-x-8 text-center lg:text-left items-start">
            <li className="flex flex-col lg:flex-row items-center lg:items-start gap-2 lg:gap-3">
              <HeartHandshake
                className="w-6 h-6 sm:w-7 sm:h-7 shrink-0 text-[#0B2545]"
                strokeWidth={1.75}
                aria-hidden="true"
              />
              <span className="text-[11px] sm:text-sm font-medium text-[#0B2545] leading-snug">
                ₹0 commissions. Always.
              </span>
            </li>
            <li className="flex flex-col lg:flex-row items-center lg:items-start gap-2 lg:gap-3">
              <Scale className="w-6 h-6 sm:w-7 sm:h-7 shrink-0 text-[#0B2545]" strokeWidth={1.75} aria-hidden="true" />
              <span className="text-[11px] sm:text-sm font-medium text-[#0B2545] leading-snug">
                IRDAI-aligned analysis
              </span>
            </li>
            <li className="flex flex-col lg:flex-row items-center lg:items-start gap-2 lg:gap-3">
              <MapPin className="w-6 h-6 sm:w-7 sm:h-7 shrink-0 text-[#0B2545]" strokeWidth={1.75} aria-hidden="true" />
              <span className="text-[11px] sm:text-sm font-medium text-[#0B2545] leading-snug">
                Built for Indian households
              </span>
            </li>
            <li className="flex flex-col lg:flex-row items-center lg:items-start gap-2 lg:gap-3">
              <Shield className="w-6 h-6 sm:w-7 sm:h-7 shrink-0 text-[#0B2545]" strokeWidth={1.75} aria-hidden="true" />
              <span className="text-[11px] sm:text-sm font-medium text-[#0B2545] leading-snug">
                Your data stays yours
              </span>
            </li>
          </ul>
        </div>
      </section>

      {/* 3 — Problems */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20" aria-labelledby="problems-heading">
        <motion.h2
          id="problems-heading"
          className="font-heading text-2xl sm:text-3xl lg:text-4xl font-bold text-[#0B2545] text-center max-w-3xl mx-auto leading-tight"
          {...fadeUp(reduceMotion)}
        >
          Why your policy probably isn&apos;t what you think it is
        </motion.h2>
        <div className="mt-10 grid md:grid-cols-3 gap-6 lg:gap-8">
          {[
            {
              title: "Hidden caps",
              line: "Room rent caps eat 40–60% of metro hospital bills.",
              body:
                "Your sum insured looks huge until sub-limits quietly shrink what the room itself can cost — and the rest comes out of pocket.",
              type: "cap",
            },
            {
              title: "Sold by commission",
              line: "Your agent earns more by selling, not by being honest.",
              body:
                "What’s “best” on paper isn’t always best for your family — incentives aren’t aligned with fine-print clarity.",
              type: "commission",
            },
            {
              title: "Wordings vs schedules",
              line: "The 50-page document you didn’t read decides everything.",
              body:
                "Schedules show numbers; wordings hide exclusions. Most people only see the brochure.",
              type: "wordings",
            },
          ].map((c) => (
            <motion.article
              key={c.title}
              className="rounded-2xl bg-white border border-[#E1E5EB] p-6 shadow-sm flex flex-col"
              {...fadeUp(reduceMotion)}
            >
              <ProblemIcon type={c.type} className="mb-4" />
              <h3 className="font-heading text-xl font-bold text-[#0B2545]">{c.title}</h3>
              <p className="mt-2 text-sm font-medium text-[#334155]">{c.line}</p>
              <p className="mt-3 text-sm text-[#64748B] leading-relaxed flex-1">{c.body}</p>
            </motion.article>
          ))}
        </div>
      </section>

      {/* 4 — How it works */}
      <section
        id="how-it-works"
        className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20 scroll-mt-24"
        aria-labelledby="how-heading"
      >
        <motion.h2
          id="how-heading"
          className="font-heading text-2xl sm:text-3xl lg:text-4xl font-bold text-[#0B2545] text-center"
          {...fadeUp(reduceMotion)}
        >
          From PDF to peace-of-mind in 3 minutes
        </motion.h2>
        <div className="mt-12 lg:mt-16 relative">
          <div
            className="hidden lg:block absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-[#13A8A8]/40 via-[#E1E5EB] to-[#E1E5EB] -translate-x-1/2 pointer-events-none"
            aria-hidden="true"
          />
          <ol className="space-y-14 lg:space-y-0 lg:grid lg:grid-cols-3 lg:gap-10 relative">
            {[
              {
                n: "1",
                t: "Upload your policy schedule",
                d: "Or tell us what you have — we’ll map it to the right audit.",
              },
              {
                n: "2",
                t: "We audit against Indian benchmarks",
                d: "Our engine checks limits, wordings, and real-world claim patterns.",
              },
              {
                n: "3",
                t: "See what you’re covered for — and what’s missing",
                d: "Scores, gaps, and plain-language findings you can act on.",
              },
            ].map((step, i) => (
              <motion.li
                key={step.n}
                className="flex flex-col items-center text-center lg:pt-0"
                {...fadeUp(reduceMotion)}
              >
                <div className="flex flex-col items-center">
                  <span className="inline-flex h-9 min-w-[2.25rem] px-2 items-center justify-center rounded-full bg-[#0B2545] text-white text-sm font-bold mb-4">
                    {step.n}
                  </span>
                  <StepVisual step={step.n} className="mb-5" />
                  <h3 className="font-heading text-lg sm:text-xl font-bold text-[#0B2545] max-w-xs">
                    {step.t}
                  </h3>
                  <p className="mt-2 text-sm text-[#64748B] max-w-sm leading-relaxed">{step.d}</p>
                </div>
                {i < 2 ? (
                  <div
                    className="lg:hidden w-px h-10 bg-[#E1E5EB] my-2"
                    aria-hidden="true"
                  />
                ) : null}
              </motion.li>
            ))}
          </ol>
        </div>
      </section>

      {/* 5 — What you get */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20" aria-labelledby="get-heading">
        <motion.h2
          id="get-heading"
          className="font-heading text-2xl sm:text-3xl lg:text-4xl font-bold text-[#0B2545] text-center max-w-3xl mx-auto"
          {...fadeUp(reduceMotion)}
        >
          Honest answers to questions your insurer won&apos;t
        </motion.h2>
        <div className="mt-12 grid lg:grid-cols-2 gap-10 lg:gap-14 items-start">
          <motion.div className="order-2 lg:order-1" {...fadeUp(reduceMotion)}>
            <ul className="space-y-4 text-[#334155]">
              {[
                "Coverage Score — what your policy actually protects against",
                "Cost Score — are you overpaying for what you have?",
                "Claim Readiness — what’ll happen when you file",
                "Gap Score — what your household is missing",
                "Specific findings, not generic advice",
              ].map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#2ECC71]/15 text-[#0F7B4F]">
                    <Check className="w-3.5 h-3.5" strokeWidth={3} aria-hidden="true" />
                  </span>
                  <span className="text-sm sm:text-base leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>
          <motion.div className="order-1 lg:order-2" {...fadeUp(reduceMotion)}>
            <DashboardMock />
          </motion.div>
        </div>
      </section>

      {/* 6 — Positioning (stacked cards) */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20" aria-labelledby="compare-heading">
        <motion.h2
          id="compare-heading"
          className="font-heading text-2xl sm:text-3xl lg:text-4xl font-bold text-[#0B2545] text-center max-w-2xl mx-auto"
          {...fadeUp(reduceMotion)}
        >
          We&apos;re not selling. We&apos;re auditing.
        </motion.h2>
        <div className="mt-10 space-y-5 max-w-xl mx-auto">
          <motion.article
            className="rounded-2xl border border-[#E1E5EB] bg-[#F8FAFC] p-6 text-[#64748B]"
            {...fadeUp(reduceMotion)}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="h-11 w-11 rounded-xl bg-white border border-[#E1E5EB] flex items-center justify-center">
                <Building2 className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className="font-heading text-lg font-bold text-[#475569]">Aggregators</h3>
            </div>
            <ul className="space-y-2 text-sm leading-relaxed">
              <li className="flex gap-2">
                <span className="text-[#94A3B8]" aria-hidden="true">
                  ·
                </span>
                Sells policies
              </li>
              <li className="flex gap-2">
                <span className="text-[#94A3B8]" aria-hidden="true">
                  ·
                </span>
                Earns commission
              </li>
              <li className="flex gap-2">
                <span className="text-[#94A3B8]" aria-hidden="true">
                  ·
                </span>
                Sorts by price
              </li>
            </ul>
          </motion.article>
          <motion.article
            className="rounded-2xl border border-[#E1E5EB] bg-[#F8FAFC] p-6 text-[#64748B]"
            {...fadeUp(reduceMotion)}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="h-11 w-11 rounded-xl bg-white border border-[#E1E5EB] flex items-center justify-center">
                <UserRound className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className="font-heading text-lg font-bold text-[#475569]">Advisors</h3>
            </div>
            <ul className="space-y-2 text-sm leading-relaxed">
              <li className="flex gap-2">
                <span className="text-[#94A3B8]" aria-hidden="true">
                  ·
                </span>
                Recommends policies
              </li>
              <li className="flex gap-2">
                <span className="text-[#94A3B8]" aria-hidden="true">
                  ·
                </span>
                Charges per consultation
              </li>
              <li className="flex gap-2">
                <span className="text-[#94A3B8]" aria-hidden="true">
                  ·
                </span>
                Sorts by advisor judgment
              </li>
            </ul>
          </motion.article>
          <motion.article
            className="rounded-2xl border-2 border-[#0B2545]/15 bg-white p-6 shadow-[0_12px_40px_rgba(11,37,69,0.1)] ring-1 ring-[#FF6B6B]/20"
            {...fadeUp(reduceMotion)}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="h-11 w-11 rounded-xl bg-[#0B2545] flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-white" aria-hidden="true" />
              </div>
              <h3 className="font-heading text-lg font-bold text-[#0B2545]">Kavachly</h3>
            </div>
            <ul className="space-y-2 text-sm text-[#334155] leading-relaxed">
              <li className="flex gap-2">
                <span className="text-[#FF6B6B] font-bold" aria-hidden="true">
                  ·
                </span>
                Audits what you already have
              </li>
              <li className="flex gap-2">
                <span className="text-[#FF6B6B] font-bold" aria-hidden="true">
                  ·
                </span>
                Free, commission-neutral
              </li>
              <li className="flex gap-2">
                <span className="text-[#FF6B6B] font-bold" aria-hidden="true">
                  ·
                </span>
                Sorts by what&apos;s actually true in your documents
              </li>
            </ul>
          </motion.article>
        </div>
      </section>

      {/* 7 — Beta */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20" aria-labelledby="beta-heading">
        <motion.div
          className="rounded-3xl bg-gradient-to-br from-[#0B2545] to-[#123a6e] px-5 py-10 sm:p-12 text-white shadow-xl"
          {...fadeUp(reduceMotion)}
        >
          <h2 id="beta-heading" className="font-heading text-2xl sm:text-3xl font-bold">
            Be first to audit yours
          </h2>
          <p className="mt-3 text-white/85 text-sm sm:text-base max-w-xl leading-relaxed">
            We&apos;re inviting 50 households to try Kavachly before public launch. No credit card. No spam. Just an
            honest look at your insurance.
          </p>
          <form id={formId} onSubmit={handleBetaSubmit} className="mt-8 space-y-4 max-w-md">
            <div>
              <label htmlFor={`${formId}-email`} className="sr-only">
                Email
              </label>
              <input
                id={`${formId}-email`}
                name="email"
                type="email"
                autoComplete="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-12 rounded-xl border border-white/20 bg-white/10 px-4 text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-[#FF6B6B]"
              />
            </div>
            <div>
              <label htmlFor={`${formId}-phone`} className="sr-only">
                Mobile number
              </label>
              <div className="flex rounded-xl border border-white/20 bg-white/10 overflow-hidden focus-within:ring-2 focus-within:ring-[#FF6B6B]">
                <span className="flex items-center px-3 text-white/70 text-sm border-r border-white/15 shrink-0">
                  +91
                </span>
                <input
                  id={`${formId}-phone`}
                  name="phone"
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel-national"
                  placeholder="10-digit mobile"
                  value={phoneLocal}
                  onChange={(e) => setPhoneLocal(e.target.value.replace(/\D/g, "").slice(0, 10))}
                  className="flex-1 min-w-0 h-12 bg-transparent px-3 text-white placeholder:text-white/50 focus:outline-none"
                  aria-describedby={`${formId}-phone-hint`}
                />
              </div>
              <p id={`${formId}-phone-hint`} className="sr-only">
                Enter 10 digits without country code
              </p>
            </div>
            <button
              type="submit"
              className="inline-flex h-12 w-full sm:w-auto items-center justify-center gap-2 rounded-xl bg-[#FF6B6B] px-8 font-semibold text-white hover:bg-[#ff5252] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-[#0B2545]"
            >
              Join the beta
              <Send className="w-4 h-4" aria-hidden="true" />
            </button>
            <p className="text-xs text-white/70 leading-relaxed">
              We&apos;ll text you when your invite is ready. We never share your info.
            </p>
          </form>
        </motion.div>
      </section>

      {/* 8 — FAQ */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20" aria-labelledby="faq-heading">
        <h2 id="faq-heading" className="font-heading text-2xl sm:text-3xl font-bold text-[#0B2545] text-center">
          Questions
        </h2>
        <Accordion type="single" collapsible className="mt-8 w-full border-t border-[#E1E5EB]">
          {[
            {
              q: "Is this free?",
              a: "Yes. The audit itself is always free.",
            },
            {
              q: "How is this different from ChatGPT?",
              a: "Kavachly is built only for Indian insurance: vertical prompts, structured audit outputs, and checks tuned to policy schedules and wordings — not generic chat.",
            },
            {
              q: "Will you sell me insurance?",
              a: "No. We’re commission-neutral by design.",
            },
            {
              q: "Is my data safe?",
              a: "Yes. Your PDF stays in our secure processing pipeline with controls appropriate for sensitive documents.",
            },
            {
              q: "What insurance types do you audit?",
              a: "Health insurance (full audit flow) and life insurance (trust panel + document path in beta). Motor and home are on the roadmap.",
            },
            {
              q: "What if I don’t have insurance yet?",
              a: "We’re built for people who already have policies. Aggregators are usually a better fit for first-time buyers.",
            },
          ].map((item, i) => (
            <AccordionItem key={item.q} value={`faq-${i}`} className="border-b border-[#E1E5EB]">
              <AccordionTrigger className="text-[#0B2545] text-base py-5 hover:no-underline">
                {item.q}
              </AccordionTrigger>
              <AccordionContent className="text-[#475569] text-sm sm:text-base leading-relaxed">
                {item.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>

      {/* 9 — Footer */}
      <footer className="border-t border-[#E1E5EB] bg-white" role="contentinfo">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-14">
          <div className="flex flex-col sm:flex-row sm:items-start gap-8 sm:gap-12">
            <div>
              <div className="inline-flex items-baseline gap-1.5">
                <ShieldCheck className="w-5 h-5 text-[#13A8A8]" strokeWidth={2.5} aria-hidden="true" />
                <span className="font-heading font-bold text-xl text-[#0B2545]">Kavachly</span>
              </div>
              <p className="mt-2 text-sm text-[#64748B]">Insurance, audited.</p>
              <p className="mt-6 text-xs text-[#94A3B8]">Made in India ❤️</p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-8 flex-1">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-[#94A3B8]">Product</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li>
                    <Link to="/audit/start" className="text-[#475569] hover:text-[#0B2545]">
                      Health audit
                    </Link>
                  </li>
                  <li>
                    <Link to="/audit/life/start" className="text-[#475569] hover:text-[#0B2545]">
                      Life audit
                    </Link>
                  </li>
                  <li>
                    <button
                      type="button"
                      onClick={scrollHow}
                      className="text-[#475569] hover:text-[#0B2545] text-left"
                    >
                      How it works
                    </button>
                  </li>
                  <li>
                    <span className="text-[#94A3B8] cursor-default">Pricing — free during beta</span>
                  </li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-[#94A3B8]">Company</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li>
                    <span className="text-[#94A3B8]">About — soon</span>
                  </li>
                  <li>
                    <span className="text-[#94A3B8]">Blog — soon</span>
                  </li>
                  <li>
                    <a href="mailto:hello@kavachly.com" className="text-[#475569] hover:text-[#0B2545]">
                      Contact
                    </a>
                  </li>
                </ul>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <p className="text-xs font-bold uppercase tracking-wider text-[#94A3B8]">Legal</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li>
                    <span className="text-[#94A3B8]">Privacy — soon</span>
                  </li>
                  <li>
                    <span className="text-[#94A3B8]">Terms — soon</span>
                  </li>
                  <li>
                    <span className="text-[#64748B] text-xs leading-snug">
                      Kavachly provides informational analysis and is not an insurer or broker. IRDAI regulations
                      apply to licensed entities; verify critical details with your policy document or advisor.
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
          <div className="mt-10 pt-8 border-t border-[#E1E5EB] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <p className="text-xs text-[#94A3B8]">
              © {new Date().getFullYear()} Kavachly. All rights reserved.
            </p>
            <div className="flex items-center gap-4">
              <a
                href="https://twitter.com/kavachly"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#64748B] hover:text-[#0B2545] text-sm"
                aria-label="Kavachly on X (Twitter)"
              >
                X
              </a>
              <a
                href="https://www.linkedin.com/company/kavachly"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#64748B] hover:text-[#0B2545] text-sm"
                aria-label="Kavachly on LinkedIn"
              >
                LinkedIn
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
