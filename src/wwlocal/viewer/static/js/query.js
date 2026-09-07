// Pure filter/sort logic over the jobs payload. No DOM, no Preact, no state of its own.

export const FACETS = {
  arrangement: j => [j.facets.arrangement],
  location: j => [j.facets.region],
  level: j => j.facets.levels,
  duration: j => [j.facets.duration],
  docs: j => j.facets.docs,
  apply: j => [j.facets.apply],
  language: j => j.languages.map(l => l.name),
};
export const FACET_LABELS = {
  arrangement: "Work mode", location: "Location", level: "Level",
  duration: "Term length", docs: "Required docs", apply: "Apply via", language: "Programming language",
};
/** Facets whose menu is grouped under a header; the header selects every option beneath it. */
export const FACET_GROUPS = {
  location: j => j.facets.country,
};
const FACET_ORDER = {
  arrangement: ["In-person", "Hybrid", "Remote"],
  level: ["Junior", "Intermediate", "Senior"],
  duration: ["4 months", "8 months preferred", "8 months required"],
  apply: ["Also on employer site", "WaterlooWorks only"],
};

export const SORTS = {
  relevance: null,  // search score, highest first; resolved in visibleJobs (needs state, not just two jobs)
  "apps-asc": (a, b) => a.application_count - b.application_count || a.id - b.id,
  "apps-desc": (a, b) => b.application_count - a.application_count || a.id - b.id,
  deadline: (a, b) => deadlineMs(a) - deadlineMs(b) || a.application_count - b.application_count,
  rating: (a, b) => (b.rating_summary.rating ?? -1) - (a.rating_summary.rating ?? -1) || b.rating_summary.rating_n - a.rating_summary.rating_n,
  hires: (a, b) => b.rating_summary.hires_total - a.rating_summary.hires_total || b.rating_summary.hires_recent - a.rating_summary.hires_recent,
  newest: (a, b) => b.id - a.id,
  org: (a, b) => a.organization.localeCompare(b.organization) || a.title.localeCompare(b.title),
  title: (a, b) => a.title.localeCompare(b.title) || a.organization.localeCompare(b.organization),
};
export const DEFAULT_SORT = "apps-asc";

function deadlineMs(j) {
  const t = j.deadline ? Date.parse(j.deadline) : NaN;
  return Number.isNaN(t) ? Infinity : t;
}

/** [[value, count], …] for one facet over `jobs`, in menu order. */
export function facetCounts(key, jobs) {
  const counts = new Map();
  for (const j of jobs) for (const v of FACETS[key](j)) counts.set(v, (counts.get(v) || 0) + 1);
  const order = FACET_ORDER[key];
  return [...counts.entries()].sort((a, b) => {
    if (order) {
      const ia = order.indexOf(a[0]), ib = order.indexOf(b[0]);
      if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    }
    return b[1] - a[1] || a[0].localeCompare(b[0]);
  });
}

/**
 * [[group, [[value, count], …], total], …] for a grouped facet, groups by size. A value that
 * occurs under two groups is listed under both, with the count for that group.
 */
export function facetGroupCounts(key, jobs) {
  const groups = new Map();
  for (const j of jobs) {
    const g = FACET_GROUPS[key](j);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(j);
  }
  return [...groups.entries()]
    .map(([g, js]) => [g, facetCounts(key, js), js.length])
    .sort((a, b) => b[2] - a[2] || a[0].localeCompare(b[0]));
}

/** Every selected facet except `except` must match (used to count a menu's own options). */
export function passesFacets(j, filters, except) {
  for (const [key, sel] of Object.entries(filters)) {
    if (key === except || !sel || !sel.length || !FACETS[key]) continue;
    const vals = FACETS[key](j);
    if (!sel.some(v => vals.includes(v))) return false;
  }
  return true;
}

/**
 * Toggles and search. Under "New only" the selected posting stays listed after it is marked
 * viewed, so selecting it doesn't yank it out from under the cursor.
 */
export function passesBase(j, { prefs, marks, selectedId, hits }) {
  const m = marks[j.id] || {};
  if (m.hidden && !prefs.showHidden) return false;
  if (prefs.onlyStar && !m.star) return false;
  if (prefs.hideApplied && m.applied) return false;
  if (prefs.onlyNew && m.viewed && j.id !== selectedId) return false;
  if (hits.scores && !hits.scores.has(j.id)) return false;
  return true;
}

/** The comparator for `sort` under `state`; relevance without a query falls back to the default. */
export function sortFn(sort, hits) {
  if (sort === "relevance") {
    if (!hits.scores) return SORTS[DEFAULT_SORT];
    return (a, b) => hits.scores.get(b.id) - hits.scores.get(a.id) || a.id - b.id;
  }
  return SORTS[sort] || SORTS[DEFAULT_SORT];
}

export function visibleJobs(state) {
  return state.jobs
    .filter(j => passesBase(j, state) && passesFacets(j, state.prefs.filters))
    .sort(sortFn(state.prefs.sort, state.hits));
}

export function anyFilterActive(prefs) {
  return Object.entries(prefs.filters).some(([k, s]) => FACETS[k] && s && s.length) || !!prefs.q || prefs.onlyStar || prefs.hideApplied || prefs.onlyNew;
}
