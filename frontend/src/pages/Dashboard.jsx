import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { Button } from "../components/ui/button";
import Header from "../components/Header";
import PortfolioHeader from "../components/dashboard/PortfolioHeader";
import CoverageByType from "../components/dashboard/CoverageByType";
import PoliciesList from "../components/dashboard/PoliciesList";
import AlertsInbox from "../components/dashboard/AlertsInbox";
import QuickActions from "../components/dashboard/QuickActions";
import DashboardEmptyState from "../components/dashboard/DashboardEmptyState";
import AddMemberModal from "../components/dashboard/AddMemberModal";
import { useAuth } from "../lib/auth";
import api from "../lib/api";

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

        {hasAudit && !loading && audit && (
          <div className="space-y-10" data-testid="dashboard-filled-state">
            <PortfolioHeader portfolio={audit.portfolio} />
            <CoverageByType
              rows={audit.portfolio.by_type}
              onViewAudit={() => navigate("/audit/report")}
            />
            <PoliciesList
              policies={policies}
              onAddPolicy={() => navigate("/audit/policies")}
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
