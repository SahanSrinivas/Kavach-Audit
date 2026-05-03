import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { MapPin, Minus, Plus, Phone } from "lucide-react";
import { toast } from "sonner";
import ProgressBar from "../components/ProgressBar";
import Header from "../components/Header";
import BottomCTA from "../components/BottomCTA";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "../components/ui/input-otp";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import api from "../lib/api";
import { useAuth } from "../lib/auth";

const POPULAR_CITIES = [
  "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata",
  "Ahmedabad", "Jaipur", "Gurugram", "Noida", "Chandigarh", "Kochi", "Lucknow",
  "Indore", "Bhopal", "Nagpur", "Coimbatore", "Visakhapatnam", "Surat",
];

async function reverseGeocode(lat, lon) {
  try {
    const r = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10`,
      { headers: { Accept: "application/json" } },
    );
    const j = await r.json();
    return (
      j?.address?.city ||
      j?.address?.town ||
      j?.address?.state_district ||
      j?.address?.state ||
      null
    );
  } catch (_) {
    return null;
  }
}

export default function Stage1Identity() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  const [age, setAge] = useState(32);
  const [city, setCity] = useState("");
  const [cityDetecting, setCityDetecting] = useState(true);
  const [citySearch, setCitySearch] = useState("");
  const [showCitySearch, setShowCitySearch] = useState(false);

  const [mobile, setMobile] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [verified, setVerified] = useState(false);

  const [sendingOtp, setSendingOtp] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Auto-detect city
  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setCityDetecting(false);
      return;
    }
    const timer = setTimeout(() => setCityDetecting(false), 6000);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const c = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        if (c) setCity(c);
        setCityDetecting(false);
        clearTimeout(timer);
      },
      () => {
        setCityDetecting(false);
        clearTimeout(timer);
      },
      { timeout: 5000, maximumAge: 1000 * 60 * 60 },
    );
    return () => clearTimeout(timer);
  }, []);

  const canSendOtp = /^\d{10}$/.test(mobile) && !otpSent;

  const handleSendOtp = async () => {
    setSendingOtp(true);
    try {
      await api.post("/auth/request-otp", { mobile });
      setOtpSent(true);
      toast.success("OTP sent", { description: "Use 123456 in development." });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send OTP");
    } finally {
      setSendingOtp(false);
    }
  };

  const handleVerifyOtp = async (value) => {
    setVerifyingOtp(true);
    try {
      await api.post("/auth/verify-otp", { mobile, otp: value });
      await refreshUser();
      setVerified(true);
      toast.success("Verified");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Invalid OTP");
      setOtp("");
    } finally {
      setVerifyingOtp(false);
    }
  };

  const handleContinue = async () => {
    setSubmitting(true);
    try {
      await api.patch("/user/me", { age, city });
      navigate("/audit/family");
    } catch (e) {
      toast.error("Couldn't save — try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const filteredCities = POPULAR_CITIES.filter((c) =>
    c.toLowerCase().includes(citySearch.toLowerCase()),
  );

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <Header />
      <ProgressBar stage={1} />

      <main className="pt-32 pb-40 md:pb-24 px-6 max-w-xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
            Step 1 of 6 · 15 seconds
          </p>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-[#0B2545] leading-tight">
            A few quick basics.
          </h1>
          <p className="mt-2 text-[#475569]">
            Three things. No name, no email, no passwords — ever.
          </p>
        </motion.div>

        {/* Age stepper */}
        <section className="mt-10" data-testid="age-section">
          <label className="text-sm font-semibold text-[#0B2545]">Your age</label>
          <div className="mt-3 flex items-center gap-4 p-3 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card">
            <Button
              data-testid="age-decrement"
              variant="ghost"
              type="button"
              onClick={() => setAge((a) => Math.max(18, a - 1))}
              className="h-11 w-11 rounded-lg hover:bg-[#F8FAFC]"
            >
              <Minus className="w-5 h-5 text-[#0B2545]" />
            </Button>
            <div className="flex-1 text-center">
              <span data-testid="age-value" className="font-heading text-4xl font-bold text-[#0B2545]">{age}</span>
              <span className="ml-1.5 text-sm text-[#475569]">yrs</span>
            </div>
            <Button
              data-testid="age-increment"
              variant="ghost"
              type="button"
              onClick={() => setAge((a) => Math.min(80, a + 1))}
              className="h-11 w-11 rounded-lg hover:bg-[#F8FAFC]"
            >
              <Plus className="w-5 h-5 text-[#0B2545]" />
            </Button>
          </div>
        </section>

        {/* City */}
        <section className="mt-8" data-testid="city-section">
          <label className="text-sm font-semibold text-[#0B2545]">Your city</label>
          {!showCitySearch ? (
            <div
              className="mt-3 flex items-center gap-3 p-4 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card cursor-pointer hover:border-[#13A8A8]/40"
              onClick={() => setShowCitySearch(true)}
              data-testid="city-chip"
            >
              <MapPin className="w-5 h-5 text-[#13A8A8]" />
              <span className="flex-1 font-medium text-[#0B2545]">
                {cityDetecting && !city ? "Detecting your city…" : city || "Tap to choose your city"}
              </span>
              <span className="text-sm text-[#13A8A8] font-semibold">Change</span>
            </div>
          ) : (
            <div className="mt-3 p-4 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card">
              <Input
                data-testid="city-search-input"
                autoFocus
                placeholder="Search your city"
                value={citySearch}
                onChange={(e) => setCitySearch(e.target.value)}
                className="h-11 border-[#E1E5EB] focus-visible:ring-[#13A8A8]"
              />
              <div className="mt-3 flex flex-wrap gap-2 max-h-48 overflow-auto">
                {filteredCities.map((c) => (
                  <button
                    key={c}
                    type="button"
                    data-testid={`city-option-${c.toLowerCase()}`}
                    onClick={() => {
                      setCity(c);
                      setShowCitySearch(false);
                      setCitySearch("");
                    }}
                    className={`px-3.5 py-2 rounded-lg text-sm font-medium border transition-colors ${
                      city === c
                        ? "bg-[#0B2545] text-white border-[#0B2545]"
                        : "bg-white text-[#475569] border-[#E1E5EB] hover:border-[#13A8A8]/40"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
              {citySearch && !filteredCities.includes(citySearch) && (
                <button
                  data-testid="city-custom-submit"
                  type="button"
                  onClick={() => {
                    setCity(citySearch);
                    setShowCitySearch(false);
                    setCitySearch("");
                  }}
                  className="mt-3 text-sm font-semibold text-[#13A8A8]"
                >
                  Use "{citySearch}"
                </button>
              )}
            </div>
          )}
        </section>

        {/* Mobile + OTP */}
        <section className="mt-8" data-testid="mobile-section">
          <label className="text-sm font-semibold text-[#0B2545]">Your mobile</label>
          <div className="mt-3 flex items-stretch gap-2">
            <div className="flex items-center gap-2 px-4 rounded-xl border border-[#E1E5EB] bg-white text-[#0B2545] font-semibold">
              <Phone className="w-4 h-4 text-[#13A8A8]" />
              +91
            </div>
            <Input
              data-testid="mobile-input"
              inputMode="numeric"
              maxLength={10}
              placeholder="10-digit number"
              value={mobile}
              onChange={(e) => {
                let v = e.target.value.replace(/\D/g, "");
                // Strip 91 country-code prefix if user pasted +91XXXXXXXXXX
                if (v.length > 10 && v.startsWith("91")) v = v.slice(2);
                setMobile(v.slice(0, 10));
              }}
              onPaste={(e) => {
                const pasted = (e.clipboardData || window.clipboardData).getData("text") || "";
                let v = pasted.replace(/\D/g, "");
                if (v.startsWith("91") && v.length > 10) v = v.slice(2);
                setMobile(v.slice(0, 10));
                e.preventDefault();
              }}
              disabled={otpSent}
              className="flex-1 h-12 text-base border-[#E1E5EB] focus-visible:ring-[#13A8A8] bg-white"
            />
            {!otpSent && (
              <Button
                data-testid="send-otp-button"
                onClick={handleSendOtp}
                disabled={!canSendOtp || sendingOtp}
                className="h-12 rounded-xl bg-[#13A8A8] hover:bg-[#13A8A8]/90 text-white font-semibold px-5"
              >
                {sendingOtp ? "…" : "Send OTP"}
              </Button>
            )}
          </div>

          <AnimatePresence>
            {otpSent && !verified && (
              <motion.div
                key="otp-block"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className="mt-5"
              >
                <p className="text-sm text-[#475569] mb-3">
                  Enter the 6-digit code sent to +91 {mobile}.{" "}
                  <span className="text-[#13A8A8] font-semibold">(Dev: 123456)</span>
                </p>
                <InputOTP
                  data-testid="otp-input"
                  maxLength={6}
                  value={otp}
                  onChange={(v) => {
                    setOtp(v);
                    if (v.length === 6) handleVerifyOtp(v);
                  }}
                  disabled={verifyingOtp}
                >
                  <InputOTPGroup>
                    {[0, 1, 2, 3, 4, 5].map((i) => (
                      <InputOTPSlot
                        key={i}
                        index={i}
                        data-testid={`otp-slot-${i}`}
                        className="w-11 h-12 text-lg border-[#E1E5EB] focus:border-[#13A8A8] focus:ring-[#13A8A8]"
                      />
                    ))}
                  </InputOTPGroup>
                </InputOTP>
                <button
                  data-testid="otp-resend-button"
                  type="button"
                  onClick={() => {
                    setOtp("");
                    setOtpSent(false);
                  }}
                  className="mt-4 text-sm text-[#475569] hover:text-[#0B2545]"
                >
                  Change number
                </button>
              </motion.div>
            )}

            {verified && (
              <motion.div
                key="verified-banner"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 px-4 py-3 rounded-lg bg-[#0F7B4F]/10 border border-[#0F7B4F]/20 text-[#0F7B4F] text-sm font-semibold"
                data-testid="otp-verified-banner"
              >
                Mobile verified. You're in.
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        <p className="mt-10 text-xs text-[#475569] max-w-md">
          We never share your number. No tele-callers — promise.
        </p>
      </main>

      <BottomCTA
        testId="stage1-continue"
        onClick={handleContinue}
        disabled={!verified || !city || !age}
        loading={submitting}
      >
        Continue
      </BottomCTA>
    </div>
  );
}
