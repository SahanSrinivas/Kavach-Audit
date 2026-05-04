import React, { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import api from "../../lib/api";

// Bottom-sheet on mobile, centered modal on desktop. Posts /family/members.
// Closes on backdrop click and on cancel; toasts on success/failure.
export default function AddMemberModal({ onClose }) {
  const [relation, setRelation] = useState("spouse");
  const [name, setName] = useState("");
  const [age, setAge] = useState(30);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.post("/family/members", {
        relation,
        name: name.trim() || undefined,
        age,
      });
      toast.success(`${name || relation} added`);
      onClose();
    } catch (_) {
      toast.error("Couldn't add");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-[#0B2545]/40 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
      onClick={onClose}
      data-testid="add-member-modal"
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl max-w-md w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-heading text-2xl font-bold text-[#0B2545]">Add a household member</h3>
        <p className="mt-1 text-sm text-[#475569]">They'll show up in your household audit.</p>

        <div className="mt-5 space-y-4">
          <div>
            <label className="text-sm font-semibold text-[#0B2545]">Relation</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {["spouse", "father", "mother", "child", "sibling", "other"].map((r) => (
                <button
                  key={r}
                  type="button"
                  data-testid={`member-rel-${r}`}
                  onClick={() => setRelation(r)}
                  className={`px-3.5 py-2 rounded-lg text-sm font-medium border ${
                    relation === r
                      ? "bg-[#0B2545] text-white border-[#0B2545]"
                      : "bg-white text-[#475569] border-[#E1E5EB] hover:border-[#13A8A8]/40"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm font-semibold text-[#0B2545]">Name (optional)</label>
            <input
              data-testid="member-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-2 w-full h-11 px-4 rounded-lg border border-[#E1E5EB] focus:ring-2 focus:ring-[#13A8A8] focus:outline-none"
              placeholder="Eg. Priya"
            />
          </div>
          <div>
            <label className="text-sm font-semibold text-[#0B2545]">Age</label>
            <input
              data-testid="member-age"
              type="number"
              value={age}
              min={0}
              max={100}
              onChange={(e) => setAge(parseInt(e.target.value || 0, 10))}
              className="mt-2 w-full h-11 px-4 rounded-lg border border-[#E1E5EB] focus:ring-2 focus:ring-[#13A8A8] focus:outline-none"
            />
          </div>
        </div>

        <div className="mt-6 flex gap-3 justify-end">
          <button
            data-testid="add-member-cancel"
            onClick={onClose}
            className="h-11 px-4 rounded-xl border border-[#E1E5EB] text-sm font-semibold text-[#0B2545]"
          >
            Cancel
          </button>
          <button
            data-testid="add-member-save"
            onClick={submit}
            disabled={submitting}
            className="h-11 px-5 rounded-xl bg-[#0B2545] text-white text-sm font-semibold disabled:opacity-50"
          >
            {submitting ? "Adding…" : "Add"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
