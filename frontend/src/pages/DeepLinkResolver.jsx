import React, { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../lib/api";

// /r/:token — resolves an alert short-link.
// If authenticated → redirect to target URL.
// Else → save token-target and send user to /login with ?next=target.
export default function DeepLinkResolver() {
  const { token } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get(`/deeplink/resolve/${token}`);
        const { target_url, authenticated } = r.data?.data || {};
        const target = target_url || "/dashboard";
        if (authenticated) {
          navigate(target, { replace: true });
        } else {
          navigate(`/login?next=${encodeURIComponent(target)}`, { replace: true });
        }
      } catch (_) {
        navigate("/login", { replace: true });
      }
    })();
  }, [token, navigate]);

  return (
    <div className="min-h-[100dvh] flex items-center justify-center">
      <div
        data-testid="deeplink-spinner"
        className="w-8 h-8 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin"
      />
    </div>
  );
}
