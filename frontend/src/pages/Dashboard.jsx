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
import LifePortfolioCard from "../components/dashboard/LifePortfolioCard";
import AlertsInbox from "../components/dashboard/AlertsInbox";
import QuickActions from "../components/dashboard/QuickActions";
import DashboardEmptyState from "../components/dashboard/DashboardEmptyState";
import DashboardErrorState from "../components/dashboard/DashboardErrorState";
import AddMemberModal from "../components/dashboard/AddMemberModal";
import PolicyDetailView from "../components/dashboard/PolicyDetailView";
import DashboardSkeleton from "../components/dashboard/DashboardSkeleton";
import useDashboardData from "../hooks/useDashboardData";
import { useAuth } from "../lib/auth";

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
  const [showAddMember, setShowAddMember] = useState(false);

  const hasAudit = user?.has_audit;
  const { audit, policies, alerts, lifeSchedules, overlapHints, retry } = useDashboardData(hasAudit);

  // "portfolio" or a policy.id. Defaults to portfolio; we auto-jump to
  // the single policy on first load when the user has exactly one
  // (single-policy users would never see useful audit-level cost or
  // gap scores otherwise).
  const [selectedPolicyId, setSelectedPolicyId] = useState("portfolio");
  const initialJumpedRef = useRef(false);

  // First-load auto-jump for single-policy users. Ref-guarded so a user
  // who manually navigates back to portfolio doesn't get yanked back in.
  useEffect(() => {
    if (initialJumpedRef.current) return;
    if (policies.loading) return;
    if (policies.data.length === 1) {
      setSelectedPolicyId(policies.data[0].id);
    }
    initialJumpedRef.current = true;
  }, [policies.loading, policies.data]);

  const onPortfolio = selectedPolicyId === "portfolio";
  const selectedPolicy = !onPortfolio
    ? policies.data.find((p) => p.id === selectedPolicyId)
    : null;

  // Edge: selected policy got deleted in another tab. Fall back to
  // portfolio rather than rendering an empty detail view.
  useEffect(() => {
    if (!onPortfolio && policies.data.length > 0 && !selectedPolicy) {
      setSelectedPolicyId("portfolio");
    }
  }, [onPortfolio, policies.data, selectedPolicy]);

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

        {hasAudit && audit.loading && <DashboardSkeleton />}

        {hasAudit && !audit.loading && audit.error && (
          <DashboardErrorState onRetry={retry.audit} />
        )}

        {hasAudit && !audit.loading && !audit.error && audit.data && !onPortfolio && selectedPolicy && (
          <PolicyDetailView
            policy={selectedPolicy}
            audit={audit.data}
            onBack={() => setSelectedPolicyId("portfolio")}
            onFixFinding={fixFinding}
          />
        )}

        {hasAudit && !audit.loading && !audit.error && audit.data && onPortfolio && (
          <div className="space-y-8" data-testid="dashboard-filled-state">
            <HeroScore
              eyebrow="Your shield"
              value={audit.data.scores?.gap ?? null}
              label={gapHeadline(audit.data.scores?.gap)}
              sublabel={gapSublabel(audit.data.scores?.gap)}
            />
            <ScoreTiles
              scores={audit.data.scores || {}}
              breakdowns={audit.data.breakdowns || {}}
            />
            <TopFindingCard
              finding={audit.data.findings?.[0] || null}
              onFix={fixFinding}
            />
            <CoverageByType
              rows={audit.data.portfolio?.by_type || []}
              onViewAudit={() => navigate("/audit/report")}
            />
            <PoliciesList
              policies={policies.data}
              findings={audit.data.all_findings || []}
              onAddPolicy={() => navigate("/audit/policies")}
              onSelectPolicy={setSelectedPolicyId}
              error={policies.error}
              retrying={policies.loading}
              onRetry={retry.policies}
            />
            <LifePortfolioCard
              schedules={lifeSchedules.data}
              overlap={overlapHints.data}
              error={lifeSchedules.error}
              overlapError={overlapHints.error}
              retrying={lifeSchedules.loading}
              overlapRetrying={overlapHints.loading}
              onRetry={() => {
                retry.lifeSchedules();
                retry.overlapHints();
              }}
              onRetryOverlap={retry.overlapHints}
              onOpenSchedule={(id) => navigate(`/audit/life/schedule?id=${encodeURIComponent(id)}`)}
              onStartLifeAudit={() => navigate("/audit/life/start")}
            />
            <AlertsInbox
              alerts={alerts.data}
              onAlertClick={(a) => {
                if (a.target_url) navigate(a.target_url);
              }}
              error={alerts.error}
              retrying={alerts.loading}
              onRetry={retry.alerts}
            />
            <QuickActions onAddMember={() => setShowAddMember(true)} />
          </div>
        )}
      </main>

      {showAddMember && <AddMemberModal onClose={() => setShowAddMember(false)} />}
    </div>
  );
}
