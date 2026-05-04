import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { Button } from "../components/ui/button";
import Header from "../components/Header";
import HeroScore from "../components/dashboard/HeroScore";
import ScoreTiles from "../components/dashboard/ScoreTiles";
import TopFindingCard from "../components/dashboard/TopFindingCard";
import CoverageByType from "../components/dashboard/CoverageByType";
import PoliciesList from "../components/dashboard/PoliciesList";
import AlertsInbox from "../components/dashboard/AlertsInbox";
import QuickActions from "../components/dashboard/QuickActions";
import DashboardEmptyState from "../components/dashboard/DashboardEmptyState";
import AddMemberModal from "../components/dashboard/AddMemberModal";
import PolicyDetailView from "../components/dashboard/PolicyDetailView";
import { useAuth } from "../lib/auth";
import api from "../lib/api";

// Portfolio-view "Your shield" hero copy keyed off the gap score band.
function gapHeadline(gap) {
  if (gap === null || gap === undefined) return "Your audit is incomplete.";
  if (gap >= 75) return "You're well-protected.";
  if (gap >= 50) return "1 critical gap to close.";
  return "Critical gaps in your cover.";
}

function gapSublabel(gap) {
  if (gap === null || gap === undefined)
    return "Re-run the audit with more data to get a score.";
  if (gap >= 75)
    return "Your portfolio covers the major risks for someone in your profile.";
  return "Tap the score tiles below to see exactly what's missing — or open the top red flag and fix it.";
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [audit, setAudit] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddMember, setShowAddMember] = useState(false);

  // "portfolio" or a policy.id. Defaults to portfolio; we auto-jump
  // to the single policy on first load when the user has exactly one
  // (single-policy users would never see useful audit-level cost or
  // gap scores otherwise).
  const [selectedPolicyId, setSelectedPolicyId] = useState("portfolio");
  const initialJumpedRef = useRef(false);

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

  // First-load auto-jump for single-policy users. Ref-guarded so a user
  // who manually navigates back to portfolio doesn't get yanked back in.
  useEffect(() => {
    if (initialJumpedRef.current) return;
    if (loading) return;
    if (policies.length === 1) {
      setSelectedPolicyId(policies[0].id);
    }
    initialJumpedRef.current = true;
  }, [loading, policies]);

  const onPortfolio = selectedPolicyId === "portfolio";
  const selectedPolicy = !onPortfolio
    ? policies.find((p) => p.id === selectedPolicyId)
    : null;

  // Edge: selected policy got deleted in another tab. Fall back to
  // portfolio rather than rendering an empty detail view.
  useEffect(() => {
    if (!onPortfolio && policies.length > 0 && !selectedPolicy) {
      setSelectedPolicyId("portfolio");
    }
  }, [onPortfolio, policies, selectedPolicy]);

  const fixFinding = (finding) => {
    navigate(`/recommendations?finding_id=${finding.id}`);
  };

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <Header />

      <main className="max-w-5xl mx-auto px-6 py-8" data-testid="dashboard-root">
        {!hasAudit ? (
          <DashboardEmptyState onTakeAudit={() => navigate("/audit/identity")} />
        ) : null}

        {hasAudit && (
          <div className="flex items-center justify-end mb-6 gap-2 text-sm">
            <span data-testid="dashboard-user-mobile" className="text-[#475569]">
              +91 {user?.mobile}
            </span>
            <Button
              data-testid="dashboard-logout-button"
              variant="ghost"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="h-8 px-2 text-[#475569] hover:text-[#0B2545]"
            >
              <LogOut className="w-4 h-4 mr-1" />
              Logout
            </Button>
          </div>
        )}

        {hasAudit && loading && (
          <div className="flex items-center justify-center py-24">
            <div className="w-8 h-8 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin" />
          </div>
        )}

        {hasAudit && !loading && audit && !onPortfolio && selectedPolicy && (
          <PolicyDetailView
            policy={selectedPolicy}
            audit={audit}
            onBack={() => setSelectedPolicyId("portfolio")}
            onFixFinding={fixFinding}
          />
        )}

        {hasAudit && !loading && audit && onPortfolio && (
          <div className="space-y-8" data-testid="dashboard-filled-state">
            <HeroScore
              eyebrow="Your shield"
              value={audit.scores?.gap ?? null}
              label={gapHeadline(audit.scores?.gap)}
              sublabel={gapSublabel(audit.scores?.gap)}
            />
            <ScoreTiles
              scores={audit.scores || {}}
              breakdowns={audit.breakdowns || {}}
            />
            <TopFindingCard
              finding={audit.findings?.[0] || null}
              onFix={fixFinding}
            />
            <CoverageByType
              rows={audit.portfolio?.by_type || []}
              onViewAudit={() => navigate("/audit/report")}
            />
            <PoliciesList
              policies={policies}
              findings={audit.all_findings || []}
              onAddPolicy={() => navigate("/audit/policies")}
              onSelectPolicy={setSelectedPolicyId}
            />
            <AlertsInbox
              alerts={alerts}
              onAlertClick={(a) => {
                if (a.target_url) navigate(a.target_url);
              }}
            />
            <QuickActions onAddMember={() => setShowAddMember(true)} />
          </div>
        )}
      </main>

      {showAddMember && <AddMemberModal onClose={() => setShowAddMember(false)} />}
    </div>
  );
}
