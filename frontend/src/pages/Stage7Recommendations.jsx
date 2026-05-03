import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, ChevronLeft, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Input } from "../components/ui/input";
import Header from "../components/Header";
import { formatINR } from "../lib/currency";
import api from "../lib/api";

export default function Stage7Recommendations() {
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const findingId = sp.get("finding_id");
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [bought, setBought] = useState(null); // selected rec id when "Buy" is clicked
  const [email, setEmail] = useState("");
  const [signedUp, setSignedUp] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/recommendations", { params: { finding_id: findingId } });
        setOptions(r.data?.data?.options || []);
      } catch (e) {
        toast.error("Couldn't load recommendations");
      } finally {
        setLoading(false);
      }
    })();
  }, [findingId]);

  const submitEarlyAccess = async (rec) => {
    if (!email || !email.includes("@")) {
      toast.error("Enter a valid email");
      return;
    }
    try {
      await api.post("/recommendations/early-access", {
        email,
        rec_id: rec.id,
        insurer: rec.insurer,
      });
      setSignedUp(true);
    } catch (e) {
      toast.error("Couldn't sign up");
    }
  };

  if (loading) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC] pb-16">
      <Header />
      <div className="border-b border-[#E1E5EB] bg-white">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-[#475569]" data-testid="recs-back">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="font-heading font-semibold text-[#0B2545]">Recommendations</span>
        </div>
      </div>

      <main className="max-w-3xl mx-auto px-6 py-8" data-testid="recs-root">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">Three options · ranked by fit</p>
          <h1 className="mt-1 font-heading text-3xl sm:text-4xl font-bold text-[#0B2545]">
            Let's fix this.
          </h1>
          <p className="mt-2 text-[#475569]">
            We rank by what fits you, not what pays us most. Commission disclosed on every card.
          </p>
        </motion.div>

        <div className="mt-8 space-y-5">
          {options.map((opt, i) => (
            <motion.article
              key={opt.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.05 }}
              className="rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card overflow-hidden"
              data-testid={`rec-card-${opt.category}`}
            >
              <div className="p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">
                      {opt.label}
                    </span>
                    <h3 className="mt-2 font-heading text-2xl font-bold text-[#0B2545]">{opt.insurer}</h3>
                    <p className="text-sm text-[#475569]">{opt.policy_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">CSR</p>
                    <p className="font-heading text-xl font-bold text-[#0F7B4F]">{opt.csr}%</p>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-[#F8FAFC]">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">Cover</p>
                    <p className="font-heading text-lg font-bold text-[#0B2545]">
                      {formatINR(opt.sum_insured, { short: true })}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-[#F8FAFC]">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#475569]">Premium / yr</p>
                    <p className="font-heading text-lg font-bold text-[#0B2545]">{formatINR(opt.premium)}</p>
                  </div>
                </div>

                <ul className="mt-5 space-y-2">
                  {opt.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-[#475569]">
                      <CheckCircle2 className="w-4 h-4 text-[#13A8A8] flex-none mt-0.5" strokeWidth={2.2} />
                      {f}
                    </li>
                  ))}
                </ul>

                <div className="mt-5 p-3 rounded-lg bg-[#13A8A8]/[0.06] border border-[#13A8A8]/15">
                  <p className="text-sm text-[#0B2545] leading-relaxed">
                    <span className="font-semibold">Why this fits you: </span>
                    {opt.fit_reason}
                  </p>
                </div>

                <p className="mt-4 text-[11px] text-[#475569]">
                  We earn {formatINR(opt.our_commission)} if you buy through Kavachly. You can also buy
                  direct from{" "}
                  <a
                    href={opt.direct_link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#13A8A8] font-medium inline-flex items-center gap-0.5"
                  >
                    {opt.insurer.toLowerCase().replace(/[^a-z]+/g, "")}.com
                    <ExternalLink className="w-3 h-3" />
                  </a>{" "}
                  and save the same.
                </p>
              </div>

              <button
                data-testid={`rec-buy-${opt.category}`}
                onClick={() => setBought(opt)}
                className="w-full py-4 bg-[#0B2545] text-white font-semibold hover:bg-[#0B2545]/90"
              >
                Buy this — 1-tap →
              </button>
            </motion.article>
          ))}
        </div>
      </main>

      {bought && (
        <div
          className="fixed inset-0 z-50 bg-[#0B2545]/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
          onClick={() => setBought(null)}
          data-testid="buy-modal"
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl max-w-md w-full p-7 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            {!signedUp ? (
              <>
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[#13A8A8]/10 mb-4">
                  <ExternalLink className="w-6 h-6 text-[#13A8A8]" />
                </div>
                <h3 className="font-heading text-2xl font-bold text-[#0B2545]">Coming soon — Phase 2</h3>
                <p className="mt-3 text-sm text-[#475569] leading-relaxed">
                  Our 1-tap quote engine is launching shortly. Drop your email and we'll get back the
                  moment {bought.insurer} is live on Kavachly.
                </p>
                <div className="mt-5 flex gap-2">
                  <Input
                    data-testid="early-access-email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-11 border-[#E1E5EB] focus-visible:ring-[#13A8A8]"
                  />
                  <button
                    data-testid="early-access-submit"
                    onClick={() => submitEarlyAccess(bought)}
                    className="h-11 px-5 rounded-xl bg-[#0B2545] text-white font-semibold whitespace-nowrap"
                  >
                    Notify me
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[#0F7B4F]/10 mb-4">
                  <CheckCircle2 className="w-6 h-6 text-[#0F7B4F]" />
                </div>
                <h3 className="font-heading text-2xl font-bold text-[#0B2545]">You're on the list.</h3>
                <p className="mt-2 text-sm text-[#475569]">
                  We'll email {email} the moment quotes go live. No spam — promise.
                </p>
                <button
                  onClick={() => {
                    setBought(null);
                    setSignedUp(false);
                    setEmail("");
                  }}
                  className="mt-5 h-11 px-5 rounded-xl bg-[#0B2545] text-white font-semibold w-full"
                >
                  Done
                </button>
              </>
            )}
          </motion.div>
        </div>
      )}
    </div>
  );
}
