import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Phone, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "../components/ui/input-otp";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import api from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const next = sp.get("next") || "/dashboard";
  const { user, refreshUser } = useAuth();

  const [mobile, setMobile] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    if (user) navigate(next, { replace: true });
  }, [user, next, navigate]);

  const canSend = /^\d{10}$/.test(mobile) && !otpSent;

  const send = async () => {
    setSending(true);
    try {
      await api.post("/auth/request-otp", { mobile });
      setOtpSent(true);
      toast.success("OTP sent", { description: "Use 123456 in development." });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send OTP");
    } finally {
      setSending(false);
    }
  };

  const verify = async (code) => {
    setVerifying(true);
    try {
      await api.post("/auth/verify-otp", { mobile, otp: code });
      await refreshUser();
      navigate(next, { replace: true });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Invalid OTP");
      setOtp("");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="min-h-[100dvh] flex flex-col bg-[#F8FAFC]">
      <header className="px-6 py-5">
        <Link to="/" data-testid="login-brand" className="inline-flex items-center gap-2 text-[#0B2545] font-semibold">
          <ShieldCheck className="w-5 h-5 text-[#13A8A8]" strokeWidth={2.5} />
          Kavach
        </Link>
      </header>

      <main className="flex-1 px-6 flex items-center">
        <div className="max-w-md w-full mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
          >
            <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#0B2545]">
              Welcome back to Kavach.
            </h1>
            <p className="mt-3 text-[#475569]">
              Enter your mobile to continue. We'll send a code — no passwords.
            </p>

            <div className="mt-8">
              <label className="text-sm font-semibold text-[#0B2545]">Mobile number</label>
              <div className="mt-2 flex items-stretch gap-2">
                <div className="flex items-center gap-2 px-4 rounded-xl border border-[#E1E5EB] bg-white text-[#0B2545] font-semibold">
                  <Phone className="w-4 h-4 text-[#13A8A8]" />
                  +91
                </div>
                <Input
                  data-testid="login-mobile-input"
                  inputMode="numeric"
                  maxLength={10}
                  placeholder="10-digit number"
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
                  disabled={otpSent}
                  className="flex-1 h-12 text-base border-[#E1E5EB] focus-visible:ring-[#13A8A8] bg-white"
                />
              </div>

              {!otpSent && (
                <Button
                  data-testid="login-send-otp"
                  onClick={send}
                  disabled={!canSend || sending}
                  className="mt-4 w-full h-12 rounded-xl bg-[#0B2545] hover:bg-[#0B2545]/90 text-white font-semibold"
                >
                  {sending ? "Sending…" : "Send OTP"}
                </Button>
              )}

              <AnimatePresence>
                {otpSent && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="mt-5"
                  >
                    <p className="text-sm text-[#475569] mb-3">
                      Enter the 6-digit code sent to +91 {mobile}.{" "}
                      <span className="text-[#13A8A8] font-semibold">(Dev: 123456)</span>
                    </p>
                    <InputOTP
                      maxLength={6}
                      value={otp}
                      onChange={(v) => {
                        setOtp(v);
                        if (v.length === 6) verify(v);
                      }}
                      disabled={verifying}
                      data-testid="login-otp-input"
                    >
                      <InputOTPGroup>
                        {[0, 1, 2, 3, 4, 5].map((i) => (
                          <InputOTPSlot
                            key={i}
                            index={i}
                            data-testid={`login-otp-slot-${i}`}
                            className="w-11 h-12 text-lg border-[#E1E5EB] focus:border-[#13A8A8] focus:ring-[#13A8A8]"
                          />
                        ))}
                      </InputOTPGroup>
                    </InputOTP>
                    <button
                      data-testid="login-change-number"
                      type="button"
                      onClick={() => {
                        setOtpSent(false);
                        setOtp("");
                      }}
                      className="mt-4 text-sm text-[#475569] hover:text-[#0B2545]"
                    >
                      Change number
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="mt-10 pt-6 border-t border-[#E1E5EB]">
              <p className="text-sm text-[#475569]">
                First time here?{" "}
                <Link to="/" data-testid="login-to-audit-link" className="text-[#13A8A8] font-semibold hover:underline">
                  Take the free audit →
                </Link>
              </p>
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  );
}
