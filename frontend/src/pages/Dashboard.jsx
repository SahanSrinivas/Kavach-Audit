import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  LogOut,
  Plus,
  Settings as SettingsIcon,
  Bell,
  ChevronRight,
  AlertTriangle,
  Info,
  RefreshCw,
  UserPlus,
  FileText,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { useAuth } from "../lib/auth";
import { formatINR } from "../lib/currency";
import api from "../lib/api";

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

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [audit, setAudit] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddMember, setShowAddMember] = useState(false);

  const hasAudit = user?.has_audit;

  useEffect(() => {
    if (!hasAudit) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const [a, p, al] = await Promise.all([
          api.get("/audit/latest"),
          api.get("/policies"),
          api.get("/alerts"),
        ]);
        setAudit(a.data?.data?.audit || null);
        setPolicies(p.data?.data?.policies || []);
        setAlerts(al.data?.data?.alerts || []);
      } finally {
        setLoading(false);
      }
    })();
  }, [hasAudit]);

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <header className="border-b border-[#E1E5EB] bg-white sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/dashboard" className="inline-flex items-center gap-2 text-[#0B2545] font-semibold">
            <ShieldCheck className="w-5 h-5 text-[#13A8A8]" strokeWidth={2.5} />
            Kavach
          </Link>
          <div className="flex items-center gap-2">
            <span data-testid="dashboard-user-mobile" className="hidden sm:inline text-sm text-[#475569]">
              +91 {user?.mobile}
            </span>
            <Button
              data-testid="dashboard-settings-link"
              variant="ghost"
              onClick={() => navigate("/dashboard/settings")}
              className="h-9 px-3 text-[#475569] hover:text-[#0B2545]"
            >
              <SettingsIcon className="w-4 h-4 sm:mr-1.5" />
              <span className="hidden sm:inline">Settings</span>
            </Button>
            <Button
              data-testid="dashboard-logout-button"
              variant="ghost"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="h-9 px-3 text-[#475569] hover:text-[#0B2545]"
            >
              <LogOut className="w-4 h-4 sm:mr-1.5" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8" data-testid="dashboard-root">
        {!hasAudit ? <EmptyState navigate={navigate} /> : null}

        {hasAudit && loading && (
          <div className="flex items-center justify-center py-24">
            <div className="w-8 h-8 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin" />
          </div>
        )}

        {hasAudit && !loading && audit && (
          <div className="space-y-10" data-testid="dashboard-filled-state">
            {/* A — Portfolio header */}
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="grid grid-cols-2 md:grid-cols-4 gap-3"
              data-testid="portfolio-header"
            >
              {[
                { l: "Total cover", v: formatINR(audit.portfolio.total_cover, { short: true }) },
                { l: "Annual premium", v: formatINR(audit.portfolio.total_premium) },
                { l: "Active policies", v: audit.portfolio.active_policies },
                {
                  l: "Next renewal",
                  v: audit.portfolio.next_renewal
                    ? new Date(audit.portfolio.next_renewal).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                      })
                    : "—",
                },
              ].map((s, i) => (
                <div key={i} className="p-5 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">{s.l}</p>
                  <p className="mt-1.5 font-heading text-2xl font-bold text-[#0B2545]">{s.v}</p>
                </div>
              ))}
            </motion.section>

            {/* B — Coverage by type */}
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="p-6 rounded-2xl bg-white border border-[#E1E5EB] kv-shadow-card"
            >
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Coverage by type</p>
              <h2 className="mt-1 font-heading text-xl font-bold text-[#0B2545]">
                Where you stand vs ideal.
              </h2>
              <div className="mt-5 space-y-3">
                {audit.portfolio.by_type.map((row) => (
                  <div key={row.type}>
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-[#0B2545]">{row.type}</span>
                      <span className="text-[#475569]">
                        {formatINR(row.current, { short: true })}{" "}
                        <span className="text-[#475569]/70">
                          / {formatINR(row.ideal, { short: true })}
                        </span>
                      </span>
                    </div>
                    <div className="mt-1.5 h-2 bg-[#E1E5EB] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          row.ratio >= 75
                            ? "bg-[#0F7B4F]"
                            : row.ratio >= 40
                              ? "bg-[#D97706]"
                              : "bg-[#B22222]"
                        }`}
                        style={{ width: `${Math.max(2, Math.min(100, row.ratio))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <button
                data-testid="dashboard-view-audit"
                onClick={() => navigate("/audit/report")}
                className="mt-6 text-sm font-semibold text-[#13A8A8] inline-flex items-center gap-1"
              >
                View full audit <ChevronRight className="w-4 h-4" />
              </button>
            </motion.section>

            {/* C — Policies */}
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              data-testid="dashboard-policies"
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Your policies</p>
                  <h2 className="mt-1 font-heading text-xl font-bold text-[#0B2545]">
                    {policies.length} active
                  </h2>
                </div>
                <button
                  data-testid="add-policy-cta"
                  onClick={() => navigate("/audit/policies")}
                  className="h-10 px-4 rounded-lg bg-white border border-[#E1E5EB] text-sm font-semibold text-[#0B2545] inline-flex items-center gap-1.5 hover:bg-[#F8FAFC]"
                >
                  <Plus className="w-4 h-4" /> Add
                </button>
              </div>
              {policies.length === 0 ? (
                <div className="p-6 rounded-xl bg-white border border-dashed border-[#E1E5EB] text-center text-sm text-[#475569]">
                  No policies on file yet. Tap Add to upload or declare.
                </div>
              ) : (
                <div className="space-y-3">
                  {policies.map((p) => (
                    <PolicyCard key={p.id} policy={p} />
                  ))}
                </div>
              )}
            </motion.section>

            {/* D — Alerts inbox */}
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
                      onClick={() => {
                        if (a.target_url) navigate(a.target_url);
                      }}
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

            {/* E — Add member / policy CTAs */}
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="grid grid-cols-1 sm:grid-cols-2 gap-4"
            >
              <button
                data-testid="add-member-cta"
                onClick={() => setShowAddMember(true)}
                className="p-5 rounded-2xl bg-white border border-[#E1E5EB] text-left hover:border-[#13A8A8]/40"
              >
                <UserPlus className="w-6 h-6 text-[#13A8A8] mb-3" />
                <p className="font-semibold text-[#0B2545]">Add a household member</p>
                <p className="mt-1 text-sm text-[#475569]">Invite spouse, parents or kids. Household view unlocks.</p>
              </button>
              <button
                data-testid="reaudit-cta-dashboard"
                onClick={async () => {
                  await api.post("/audit/generate");
                  toast.success("Re-audit complete");
                  window.location.reload();
                }}
                className="p-5 rounded-2xl bg-white border border-[#E1E5EB] text-left hover:border-[#13A8A8]/40"
              >
                <RefreshCw className="w-6 h-6 text-[#13A8A8] mb-3" />
                <p className="font-semibold text-[#0B2545]">Re-run my audit</p>
                <p className="mt-1 text-sm text-[#475569]">Anything changed? Get fresh scores in 30 seconds.</p>
              </button>
            </motion.section>
          </div>
        )}
      </main>

      {showAddMember && <AddMemberModal onClose={() => setShowAddMember(false)} />}
    </div>
  );
}

function EmptyState({ navigate }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="text-center max-w-xl mx-auto py-16"
      data-testid="dashboard-empty-state"
    >
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#13A8A8]/10 mb-8">
        <Sparkles className="w-7 h-7 text-[#13A8A8]" strokeWidth={2} />
      </div>
      <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#0B2545]">
        You haven't run your audit yet.
      </h1>
      <p className="mt-4 text-[#475569] text-base sm:text-lg leading-relaxed">
        Takes about 60 seconds. You'll get four scores, the top three red flags in your current
        policies, and a plain-English plan to fix them.
      </p>
      <Button
        data-testid="dashboard-take-audit"
        onClick={() => navigate("/audit/identity")}
        className="mt-10 h-14 px-8 rounded-xl bg-[#0B2545] hover:bg-[#0B2545]/90 text-white font-semibold text-base"
      >
        Take 60-second audit →
      </Button>
      <p className="mt-6 text-xs text-[#475569]">We don't sell. We audit.</p>
    </motion.div>
  );
}

function PolicyCard({ policy }) {
  const flagCount = policy.parsed_fields?.sub_limits?.length || 0;
  const flagState = flagCount === 0 ? "ok" : flagCount <= 2 ? "warn" : "critical";
  const badge =
    flagState === "ok"
      ? { label: "✓ no issues", cls: "text-[#0F7B4F] bg-[#0F7B4F]/10" }
      : flagState === "warn"
        ? { label: `⚠ ${flagCount} red flags`, cls: "text-[#D97706] bg-[#D97706]/10" }
        : { label: `🚩 ${flagCount} critical`, cls: "text-[#B22222] bg-[#B22222]/10" };
  return (
    <article
      data-testid={`policy-card-${policy.id}`}
      className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card flex items-start gap-4"
    >
      <span className="w-12 h-12 rounded-lg bg-[#13A8A8]/10 flex items-center justify-center flex-none">
        <FileText className="w-5 h-5 text-[#13A8A8]" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold text-[#0B2545] truncate">{policy.insurer}</p>
            <p className="text-sm text-[#475569]">
              {policy.policy_name || policy.type} · cover {formatINR(policy.sum_insured, { short: true })}
            </p>
          </div>
          <span className={`text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md whitespace-nowrap ${badge.cls}`}>
            {badge.label}
          </span>
        </div>
        <p className="mt-1.5 text-xs text-[#475569]">
          Premium {formatINR(policy.premium)} / yr
          {policy.end_date && (
            <>
              {" · "}Renews{" "}
              {new Date(policy.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
            </>
          )}
        </p>
      </div>
    </article>
  );
}

function AddMemberModal({ onClose }) {
  const [relation, setRelation] = useState("spouse");
  const [name, setName] = useState("");
  const [age, setAge] = useState(30);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.post("/family/members", {
        relation,
        name: name.trim() || undefined,
        age,
      });
      toast.success(`${name || relation} added`);
      onClose();
    } catch (_) {
      toast.error("Couldn't add");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-[#0B2545]/40 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
      onClick={onClose}
      data-testid="add-member-modal"
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl max-w-md w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-heading text-2xl font-bold text-[#0B2545]">Add a household member</h3>
        <p className="mt-1 text-sm text-[#475569]">They'll show up in your household audit.</p>

        <div className="mt-5 space-y-4">
          <div>
            <label className="text-sm font-semibold text-[#0B2545]">Relation</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {["spouse", "father", "mother", "child", "sibling", "other"].map((r) => (
                <button
                  key={r}
                  type="button"
                  data-testid={`member-rel-${r}`}
                  onClick={() => setRelation(r)}
                  className={`px-3.5 py-2 rounded-lg text-sm font-medium border ${
                    relation === r
                      ? "bg-[#0B2545] text-white border-[#0B2545]"
                      : "bg-white text-[#475569] border-[#E1E5EB] hover:border-[#13A8A8]/40"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm font-semibold text-[#0B2545]">Name (optional)</label>
            <input
              data-testid="member-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-2 w-full h-11 px-4 rounded-lg border border-[#E1E5EB] focus:ring-2 focus:ring-[#13A8A8] focus:outline-none"
              placeholder="Eg. Priya"
            />
          </div>
          <div>
            <label className="text-sm font-semibold text-[#0B2545]">Age</label>
            <input
              data-testid="member-age"
              type="number"
              value={age}
              min={0}
              max={100}
              onChange={(e) => setAge(parseInt(e.target.value || 0, 10))}
              className="mt-2 w-full h-11 px-4 rounded-lg border border-[#E1E5EB] focus:ring-2 focus:ring-[#13A8A8] focus:outline-none"
            />
          </div>
        </div>

        <div className="mt-6 flex gap-3 justify-end">
          <button
            data-testid="add-member-cancel"
            onClick={onClose}
            className="h-11 px-4 rounded-xl border border-[#E1E5EB] text-sm font-semibold text-[#0B2545]"
          >
            Cancel
          </button>
          <button
            data-testid="add-member-save"
            onClick={submit}
            disabled={submitting}
            className="h-11 px-5 rounded-xl bg-[#0B2545] text-white text-sm font-semibold disabled:opacity-50"
          >
            {submitting ? "Adding…" : "Add"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
