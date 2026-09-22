import { useEffect, useState } from "react";

// Amendment 41 (Section 47): live clock + time-of-day greeting in the top
// bar. Pure client-side, real system time -- honest by construction, no
// backend involved. Deliberately does NOT include an activity ticker
// (see Section-47-specs.md Open Decision 2: that's the same concept as
// the "Recent Activity" feed Amendment 12 removed for being noise, not
// signal -- not rebuilt here).
function greeting(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function formatTime(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export default function LiveClock({ name }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <p className="text-xs text-text-secondary text-right leading-tight font-mono">
      {greeting(now.getHours())}, {name} &middot; {formatTime(now)}
    </p>
  );
}
