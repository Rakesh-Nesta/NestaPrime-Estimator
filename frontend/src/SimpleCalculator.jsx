import { useState } from "react";

// Amendment 12 (Section 11): "basic + - x / % calculator idea if user
// don't have calculator for some basic calculation needed" -- a plain
// arithmetic widget under Tools, unrelated to the Pricing Calculator.
// Purely client-side, no backend.
const OPS = { "÷": (a, b) => a / b, "×": (a, b) => a * b, "−": (a, b) => a - b, "+": (a, b) => a + b };

export default function SimpleCalculator({ onBack }) {
  const [display, setDisplay] = useState("0");
  const [stored, setStored] = useState(null);
  const [pendingOp, setPendingOp] = useState(null);
  const [overwrite, setOverwrite] = useState(true);

  function inputDigit(digit) {
    if (overwrite) {
      setDisplay(digit === "." ? "0." : digit);
      setOverwrite(false);
    } else if (digit === "." && display.includes(".")) {
      // no-op: only one decimal point allowed
    } else {
      setDisplay(display === "0" && digit !== "." ? digit : display + digit);
    }
  }

  function applyOp(nextOp) {
    const current = parseFloat(display);
    if (stored === null) {
      setStored(current);
    } else if (pendingOp) {
      setStored(OPS[pendingOp](stored, current));
    }
    setPendingOp(nextOp);
    setOverwrite(true);
  }

  function handleEquals() {
    if (pendingOp === null || stored === null) return;
    const result = OPS[pendingOp](stored, parseFloat(display));
    setDisplay(String(result));
    setStored(null);
    setPendingOp(null);
    setOverwrite(true);
  }

  function handlePercent() {
    setDisplay(String(parseFloat(display) / 100));
    setOverwrite(true);
  }

  function handleClear() {
    setDisplay("0");
    setStored(null);
    setPendingOp(null);
    setOverwrite(true);
  }

  const buttons = [
    ["7", "8", "9", "÷"],
    ["4", "5", "6", "×"],
    ["1", "2", "3", "−"],
    ["0", ".", "%", "+"],
  ];

  return (
    <div className="max-w-xs mx-auto mt-8 mb-10 space-y-6 px-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading font-bold text-text-primary text-lg">Calculator</h2>
        {onBack && (
          <button onClick={onBack} className="text-sm text-gold hover:underline">
            &larr; Back
          </button>
        )}
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-4 space-y-3">
        <div className="bg-base border border-border-dark rounded px-3 py-4 text-right">
          <p className="font-mono text-2xl text-text-primary truncate">{display}</p>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <button
            onClick={handleClear}
            className="col-span-4 bg-surface-raised text-text-secondary rounded px-3 py-2.5 text-sm font-semibold hover:bg-border-dark hover:-translate-y-0.5 transition-all duration-250 ease-out"
          >
            Clear
          </button>
          {buttons.map((row) =>
            row.map((label) => (
              <button
                key={label}
                onClick={() => {
                  if (label === "%") handlePercent();
                  else if (label in OPS) applyOp(label);
                  else inputDigit(label);
                }}
                className={`rounded px-3 py-2.5 text-sm font-semibold hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                  label in OPS || label === "%"
                    ? pendingOp === label
                      ? "bg-gold-hover text-base"
                      : "bg-gold text-base hover:bg-gold-hover"
                    : "bg-surface-raised text-text-primary hover:bg-border-dark"
                }`}
              >
                {label}
              </button>
            ))
          )}
          <button
            onClick={handleEquals}
            className="col-span-4 bg-gold text-base rounded px-3 py-2.5 text-sm font-semibold hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out"
          >
            =
          </button>
        </div>
      </div>
    </div>
  );
}
