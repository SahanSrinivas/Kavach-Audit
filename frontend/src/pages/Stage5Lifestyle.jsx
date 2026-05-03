import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import ProgressBar from "../components/ProgressBar";
import BottomCTA from "../components/BottomCTA";
import api from "../lib/api";

const QUESTIONS = [
  { id: "smoker", q: "Do you smoke or chew tobacco?" },
  { id: "travels_intl", q: "Travel internationally 2+ times per year?" },
  { id: "two_wheeler", q: "Two-wheeler rider for daily commute?" },
  { id: "self_employed", q: "Self-employed or business owner?" },
];

const EVENTS = ["Marriage", "Baby", "Home loan", "Job change abroad", "None"];

export default function Stage5Lifestyle() {
  const navigate = useNavigate();
  const [answers, setAnswers] = useState({});
  const [events, setEvents] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);

  const allAnswered = QUESTIONS.every((q) => answers[q.id] !== undefined);

  const toggleEvent = (e) => {
    setEvents((prev) => {
      if (e === "None") return ["None"];
      const cleaned = prev.filter((x) => x !== "None");
      return cleaned.includes(e) ? cleaned.filter((x) => x !== e) : [...cleaned, e];
    });
  };

  const handleGenerate = async () => {
    setSubmitting(true);
    try {
      await api.patch("/user/me", {
        lifestyle: { ...answers, planned_events: events },
      });
      setGenerating(true);
      // 3-second loading screen with rotating reassurance
      await new Promise((r) => setTimeout(r, 3000));
      await api.post("/audit/generate");
      navigate("/audit/report");
    } catch (e) {
      setGenerating(false);
      setSubmitting(false);
    }
  };

  if (generating) return <GeneratingScreen />;

  return (
    <div className="min-h-[100dvh] bg-[#F8FAFC]">
      <ProgressBar stage={5} />
      <main className="pt-20 pb-40 md:pb-24 px-6 max-w-xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8] mb-3">
            Step 5 of 6 · 15 seconds
          </p>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-[#0B2545] leading-tight">
            Five quick taps. Each one
            <br />
            changes your recommendations.
          </h1>
        </motion.div>

        <section className="mt-8 space-y-5">
          {QUESTIONS.map((q) => (
            <div
              key={q.id}
              className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card"
              data-testid={`q-${q.id}`}
            >
              <p className="text-sm font-semibold text-[#0B2545] mb-3">{q.q}</p>
              <div className="flex bg-[#E1E5EB]/40 p-1 rounded-xl">
                {[
                  { v: true, l: "Yes" },
                  { v: false, l: "No" },
                ].map((opt) => (
                  <button
                    key={String(opt.v)}
                    type="button"
                    data-testid={`q-${q.id}-${opt.l.toLowerCase()}`}
                    onClick={() => setAnswers((a) => ({ ...a, [q.id]: opt.v }))}
                    className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                      answers[q.id] === opt.v ? "bg-white text-[#0B2545] shadow-sm" : "text-[#475569]"
                    }`}
                  >
                    {opt.l}
                  </button>
                ))}
              </div>
            </div>
          ))}

          <div
            className="p-5 rounded-xl bg-white border border-[#E1E5EB] kv-shadow-card"
            data-testid="q-planned-events"
          >
            <p className="text-sm font-semibold text-[#0B2545] mb-3">
              Any planned life events in the next 2 years?
            </p>
            <div className="flex flex-wrap gap-2">
              {EVENTS.map((e) => (
                <button
                  key={e}
                  type="button"
                  data-testid={`event-${e.toLowerCase().replace(/\s+/g, "-")}`}
                  onClick={() => toggleEvent(e)}
                  className={`px-3.5 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    events.includes(e)
                      ? "bg-[#0B2545] text-white border-[#0B2545]"
                      : "bg-white text-[#475569] border-[#E1E5EB] hover:border-[#13A8A8]/40"
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>
        </section>
      </main>

      <BottomCTA
        testId="stage5-generate"
        onClick={handleGenerate}
        disabled={!allAnswered || events.length === 0}
        loading={submitting}
      >
        Generate my audit →
      </BottomCTA>
    </div>
  );
}

function GeneratingScreen() {
  const [idx, setIdx] = useState(0);
  const messages = [
    "Comparing 40+ insurers…",
    "Reading every clause…",
    "Calculating your scores…",
  ];
  React.useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % messages.length), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="min-h-[100dvh] flex flex-col items-center justify-center px-6 bg-[#F8FAFC]" data-testid="generating-screen">
      <div className="w-12 h-12 border-4 border-[#E1E5EB] border-t-[#13A8A8] rounded-full animate-spin" />
      <motion.p
        key={idx}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mt-8 font-heading text-2xl font-semibold text-[#0B2545] text-center"
      >
        {messages[idx]}
      </motion.p>
    </div>
  );
}
