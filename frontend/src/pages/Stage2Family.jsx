import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { User, Users, Baby, HeartPulse, Home as HomeIcon } from "lucide-react";
import ProgressBar from "../components/ProgressBar";
import Header from "../components/Header";
import BottomCTA from "../components/BottomCTA";
import Chip from "../components/Chip";
import KvSlider from "../components/KvSlider";
import api from "../lib/api";

const COMPOSITIONS = [
  { value: "self", icon: User, label: "Just me" },
  { value: "self_spouse", icon: Users, label: "Me + spouse" },
  { value: "self_spouse_kids", icon: Baby, label: "Me + spouse + kids" },
  { value: "self_parents", icon: HeartPulse, label: "Me + parents" },
  { value: "full_family", icon: HomeIcon, label: "Full family (spouse + kids + parents)" },
];

const PEC_OPTIONS = ["None", "Diabetes", "BP", "Heart", "Other", "Prefer not to say"];

export default function Stage2Family() {
  const navigate = useNavigate();
  const [composition, setComposition] = useState("");
  const [spouseAge, setSpouseAge] = useState(30);
  const [kidsCount, setKidsCount] = useState(1);
  const [kidsYoungestAge, setKidsYoungestAge] = useState(5);
  const [motherAge, setMotherAge] = useState(60);
  const [fatherAge, setFatherAge] = useState(65);
  const [pec, setPec] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const hasSpouse = ["self_spouse", "self_spouse_kids", "full_family"].includes(composition);
  const hasKids = ["self_spouse_kids", "full_family"].includes(composition);
  const hasParents = ["self_parents", "full_family"].includes(composition);

  const togglePec = (v) => {
    setPec((prev) => {
      if (v === "None" || v === "Prefer not to say") return [v];
      const cleaned = prev.filter((x) => x !== "None" && x !== "Prefer not to say");
      return cleaned.includes(v) ? cleaned.filter((x) => x !== v) : [...cleaned, v];
    });
  };

  const handleContinue = async () => {
    setSubmitting(true);
    try {
      await api.patch("/user/me", {
        family_composition: composition,
        spouse_age: hasSpouse ? spouseAge : null,
        kids_count: hasKids ? kidsCount : null,
        kids_youngest_age: hasKids ? kidsYoungestAge : null,
        parents_ages: hasParents ? { mother: motherAge, father: fatherAge } : null,
        parents_pec: hasParents ? pec : null,
      });
      navigate("/audit/money");
    } catch (e) {
      toast.error("Couldn't save — try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <Header />
      <ProgressBar stage={2} />
      <main className="pt-32 pb-40 md:pb-24 px-6 max-w-xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
            Step 2 of 6 · 20 seconds
          </p>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-[#0B2545] leading-tight">
            Who do you need to protect?
          </h1>
        </motion.div>

        <section className="mt-8 space-y-3" data-testid="composition-section">
          {COMPOSITIONS.map((c) => {
            const Icon = c.icon;
            return (
              <Chip
                key={c.value}
                active={composition === c.value}
                onClick={() => setComposition(c.value)}
                testId={`composition-${c.value}`}
              >
                <Icon className="w-4 h-4 text-[#13A8A8]" strokeWidth={2.2} />
                {c.label}
              </Chip>
            );
          })}
        </section>

        <AnimatePresence>
          {hasSpouse && (
            <motion.section
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-8 p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card"
              data-testid="spouse-section"
            >
              <KvSlider
                testId="spouse-age-slider"
                label="Spouse's age"
                value={spouseAge}
                onChange={setSpouseAge}
                min={18}
                max={80}
                formatValue={(v) => `${v} yrs`}
              />
            </motion.section>
          )}

          {hasKids && (
            <motion.section
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-6 p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card space-y-5"
              data-testid="kids-section"
            >
              <div>
                <label className="text-sm font-semibold text-[#0B2545] mb-3 block">
                  Number of kids
                </label>
                <div className="flex bg-[#E1E5EB]/40 p-1 rounded-xl">
                  {[1, 2, 3].map((n) => (
                    <button
                      key={n}
                      type="button"
                      data-testid={`kids-count-${n}`}
                      onClick={() => setKidsCount(n)}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                        kidsCount === n ? "bg-white text-[#0B2545] shadow-sm" : "text-[#475569]"
                      }`}
                    >
                      {n === 3 ? "3+" : n}
                    </button>
                  ))}
                </div>
              </div>
              <KvSlider
                testId="kids-youngest-slider"
                label="Youngest kid's age"
                value={kidsYoungestAge}
                onChange={setKidsYoungestAge}
                min={0}
                max={25}
                formatValue={(v) => (v === 0 ? "Newborn" : `${v} yrs`)}
              />
            </motion.section>
          )}

          {hasParents && (
            <motion.section
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-6 p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card space-y-5"
              data-testid="parents-section"
            >
              <KvSlider
                testId="mother-age-slider"
                label="Mother's age"
                value={motherAge}
                onChange={setMotherAge}
                min={40}
                max={90}
                formatValue={(v) => `${v} yrs`}
              />
              <KvSlider
                testId="father-age-slider"
                label="Father's age"
                value={fatherAge}
                onChange={setFatherAge}
                min={40}
                max={90}
                formatValue={(v) => `${v} yrs`}
              />
              <div>
                <label className="text-sm font-semibold text-[#0B2545] mb-3 block">
                  Any pre-existing conditions in parents?
                </label>
                <div className="flex flex-wrap gap-2" data-testid="pec-chip-row">
                  {PEC_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      data-testid={`pec-${opt.toLowerCase().replace(/\s+/g, "-")}`}
                      onClick={() => togglePec(opt)}
                      className={`px-3.5 py-2 rounded-lg text-sm font-medium border transition-colors ${
                        pec.includes(opt)
                          ? "bg-[#0B2545] text-white border-[#0B2545]"
                          : "bg-white text-[#475569] border-[#E1E5EB] hover:border-[#13A8A8]/40"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            </motion.section>
          )}
        </AnimatePresence>
      </main>

      <BottomCTA
        testId="stage2-continue"
        onClick={handleContinue}
        disabled={!composition}
        loading={submitting}
      >
        Continue
      </BottomCTA>
    </div>
  );
}
