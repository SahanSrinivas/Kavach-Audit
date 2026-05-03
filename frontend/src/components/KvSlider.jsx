import React from "react";
import { Slider } from "./ui/slider";

// Wrapper around shadcn Slider with Kavachly styling and live label.
export default function KvSlider({
  value,
  onChange,
  min,
  max,
  step = 1,
  formatValue,
  label,
  hint,
  testId,
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <label className="text-sm font-semibold text-[#0B2545]">{label}</label>
        <span
          data-testid={`${testId}-value`}
          className="font-heading text-lg font-bold text-[#13A8A8]"
        >
          {formatValue ? formatValue(value) : value}
        </span>
      </div>
      <Slider
        data-testid={testId}
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(v[0])}
        className="kv-slider"
      />
      {hint && <p className="text-xs text-[#475569]">{hint}</p>}
    </div>
  );
}
