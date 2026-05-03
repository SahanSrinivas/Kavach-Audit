import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { LinkIcon } from "lucide-react";
import api from "../lib/api";

// /r/:token resolver
// - Valid token + auth → redirect to target_url
// - Valid token, no auth → /login?next=<target>
// - Invalid/expired token → friendly screen with CTA back to /
export default function DeepLinkResolver() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("loading"); // loading | invalid

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get(`/deeplink/resolve/${token}`);
        const { target_url, authenticated } = r.data?.data || {};
        const target = target_url || "/dashboard";
        if (authenticated) navigate(target, { replace: true });
        else navigate(`/login?next=${encodeURIComponent(target)}`, { replace: true });
      } catch (e) {
        if (e.response?.status === 404) setStatus("invalid");
        else navigate("/login", { replace: true });
      }
    })();
  }, [token, navigate]);

  if (status === "loading") {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center">
        <div
          data-testid="deeplink-spinner"
          className="w-8 h-8 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin"
        />
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] flex items-center justify-center px-6 bg-[#F8FAFC]" data-testid="deeplink-invalid">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="max-w-md w-full text-center"
      >
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#B22222]/10 mb-6">
          <LinkIcon className="w-6 h-6 text-[#B22222]" />
        </div>
        <h1 className="font-heading text-3xl font-bold text-[#0B2545]">Link expired</h1>
        <p className="mt-3 text-[#475569]">
          This alert link is no longer valid or has already been used. Sign in to view your dashboard.
        </p>
        <Link
          to="/"
          data-testid="deeplink-back-cta"
          className="mt-8 inline-flex h-12 px-6 items-center rounded-xl bg-[#0B2545] text-white font-semibold"
        >
          Go to Kavachly
        </Link>
      </motion.div>
    </div>
  );
}
