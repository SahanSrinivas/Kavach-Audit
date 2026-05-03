import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ChevronLeft, LogOut, Smartphone, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import api from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/auth/sessions");
      setSessions(r.data?.data?.sessions || []);
    } catch (_) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const revoke = async (id) => {
    try {
      await api.delete(`/auth/sessions/${id}`);
      toast.success("Session revoked");
      load();
    } catch (_) {
      toast.error("Could not revoke");
    }
  };

  const logoutAll = async () => {
    try {
      await api.post("/auth/logout-all");
    } catch (_) {}
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <header className="border-b border-[#E1E5EB] bg-white">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center gap-3">
          <Link to="/dashboard" data-testid="settings-back" className="text-[#475569] hover:text-[#0B2545]">
            <ChevronLeft className="w-5 h-5" />
          </Link>
          <ShieldCheck className="w-5 h-5 text-[#13A8A8]" />
          <h1 className="font-heading font-semibold text-[#0B2545]">Settings</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10" data-testid="settings-root">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="bg-white rounded-xl border border-[#E1E5EB] p-6 kv-shadow-card"
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Account</p>
          <div className="mt-4 flex items-center gap-3">
            <Smartphone className="w-5 h-5 text-[#0B2545]" />
            <span data-testid="settings-mobile" className="font-semibold text-[#0B2545]">
              +91 {user?.mobile}
            </span>
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.05 }}
          className="mt-6 bg-white rounded-xl border border-[#E1E5EB] p-6 kv-shadow-card"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Active Sessions</p>
            <Button
              data-testid="settings-logout-all"
              onClick={logoutAll}
              variant="ghost"
              className="h-8 text-[#B22222] hover:bg-[#B22222]/10"
            >
              <LogOut className="w-4 h-4 mr-1.5" />
              Logout from all devices
            </Button>
          </div>

          <div className="mt-4 divide-y divide-[#E1E5EB]" data-testid="settings-sessions-list">
            {loading && <p className="text-sm text-[#475569] py-4">Loading…</p>}
            {!loading && sessions.length === 0 && (
              <p className="text-sm text-[#475569] py-4">No sessions.</p>
            )}
            {sessions.map((s) => (
              <div key={s.id} className="py-4 flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p
                    className="text-sm font-semibold text-[#0B2545] truncate"
                    data-testid={`session-ua-${s.id}`}
                  >
                    {s.user_agent || "Unknown device"}{" "}
                    {s.is_current && (
                      <span className="ml-2 text-xs font-medium text-[#13A8A8]">current</span>
                    )}
                  </p>
                  <p className="text-xs text-[#475569] mt-0.5">
                    Last used {new Date(s.last_used_at).toLocaleString("en-IN")}
                  </p>
                </div>
                {!s.is_current && (
                  <Button
                    data-testid={`session-revoke-${s.id}`}
                    onClick={() => revoke(s.id)}
                    variant="ghost"
                    className="h-9 text-[#B22222] hover:bg-[#B22222]/10"
                  >
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="mt-6"
        >
          <Button
            data-testid="settings-logout"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            className="h-12 rounded-xl bg-white border border-[#E1E5EB] text-[#0B2545] hover:bg-[#F8FAFC] w-full sm:w-auto px-8"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout this device
          </Button>
        </motion.section>
      </main>
    </div>
  );
}
