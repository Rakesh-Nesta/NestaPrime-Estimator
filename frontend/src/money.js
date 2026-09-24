// Amendment 50 (Section 54): one place for how a rupee amount is written, so the
// Payments screen, the Work Order panel and the Overview never disagree.
export function formatRs(value) {
  return `Rs ${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

// Whole rupees, for a tile where paise would only crowd the number.
export function formatRsWhole(value) {
  return `Rs ${Math.round(Number(value)).toLocaleString("en-IN")}`;
}
