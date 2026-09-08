// Small formatting helpers shared by the components. Pure functions.

export function fmtDate(d, opts) {
  return d ? new Date(d).toLocaleDateString("en-CA", opts || { month: "short", day: "numeric" }) : "—";
}
export const DATE_TIME = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };

export function relTime(iso) {
  const m = Math.round((Date.now() - new Date(iso)) / 6e4);
  if (m < 2) return "just now";
  if (m < 60) return m + " min ago";
  const h = Math.round(m / 60);
  if (h < 36) return h + " h ago";
  return Math.round(h / 24) + " days ago";
}

/** "up" / "down" / "" for a rating against the all-students average; "" if the report has no average. */
export function ratingClass(rating, allAvg) {
  if (allAvg == null) return "";
  const diff = rating - allAvg;
  return diff >= 0.3 ? "up" : diff <= -0.3 ? "down" : "";
}

/** "2025 - Fall" → "F 2025" for chart labels. */
export function termLabel(t) {
  const [y, s] = String(t).split(" - ");
  return s ? s[0] + " " + y : t;
}

export const COMP_UNIT_LABEL = { hr: "hourly", wk: "per week", mo: "per month", yr: "per year", term: "per term" };
const COMP_HOURS = { hr: 1, wk: 40, mo: 173.3, yr: 2080, term: 640 };
const COMP_SUFFIX = { hr: "/hr", wk: "/wk", mo: "/mo", yr: "/yr", term: "/term" };

export function fmtMoney(n, sym) {
  return sym + (n >= 1000 || Number.isInteger(n) ? Math.round(n).toLocaleString("en-CA") : n.toFixed(2).replace(/\.?0+$/, ""));
}
export function compLabel(c) {
  const sym = c.currency === "EUR" ? "€" : "$";
  return fmtMoney(c.lo, sym) + (c.hi != null ? "–" + fmtMoney(c.hi, "") : "") + COMP_SUFFIX[c.unit];
}
export function compHourly(c) {
  const mid = c.hi != null ? (c.lo + c.hi) / 2 : c.lo;
  return mid / COMP_HOURS[c.unit];
}

/** "required_skills" → "Required skills", for field keys without a hand-written label. */
export function humanize(key) {
  return key.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
}

// Bare URLs, www. hosts and email addresses in prose. Trailing punctuation is left out of the match
// so "see https://x.com/jobs." links to the page, not to "jobs.".
const LINK_RE = /\b(?:https?:\/\/[^\s<>"'()]+|www\.[^\s<>"'()]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)/g;

/** Split text into [{text}] and [{text, href}] segments, so callers can render links however they like. */
export function linkSegments(text) {
  const out = [];
  let last = 0;
  for (const m of String(text).matchAll(LINK_RE)) {
    let hit = m[0].replace(/[.,;:!?]+$/, "");
    if (!hit) continue;
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    const href = hit.includes("@") && !/^https?:/.test(hit) ? "mailto:" + hit : /^www\./i.test(hit) ? "https://" + hit : hit;
    out.push({ text: hit, href });
    last = m.index + hit.length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}
