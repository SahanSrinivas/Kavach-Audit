// Indian number formatting: ₹1,23,456 / lakhs / crores
export function formatINR(amount, opts = {}) {
  const { short = false } = opts;
  if (amount == null || Number.isNaN(+amount)) return "₹0";
  const n = +amount;
  if (short) {
    if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(n % 1_00_00_000 === 0 ? 0 : 1)}Cr`;
    if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(n % 1_00_000 === 0 ? 0 : 1)}L`;
    if (n >= 1_000) return `₹${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`;
    return `₹${n}`;
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
}
