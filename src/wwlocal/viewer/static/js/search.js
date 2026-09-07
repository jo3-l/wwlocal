// Full-text search over the jobs payload, wrapping the vendored MiniSearch. Pure: no DOM, no
// state of its own. store.js builds one index the first time a query is typed and re-runs the
// query as it changes. MiniSearch itself is imported lazily, so a session that never searches
// never fetches it.

const FIELDS = ["title", "organization", "division", "city", "summary", "responsibilities", "required_skills", "compensation", "clusters"];

const SEARCH_OPTIONS = {
  combineWith: "AND",              // every query word must match, as the old substring search did
  prefix: true,                    // "learn" matches "learning"
  fuzzy: term => term.length > 3 ? 0.2 : false,  // one edit in a 5-letter word; short words stay exact
  boost: { title: 3, organization: 2 },
};

/** A posting flattened to the fields the index covers. */
function toDoc(j) {
  const d = j.detail || {};
  return {
    id: j.id, title: j.title, organization: j.organization, division: j.division, city: j.city,
    summary: d.summary, responsibilities: d.responsibilities, required_skills: d.required_skills,
    compensation: d.compensation, clusters: j.facets.clusters.join(" "),
  };
}

export async function buildIndex(jobs) {
  const { default: MiniSearch } = await import("../vendor/minisearch.mjs");
  const index = new MiniSearch({ fields: FIELDS, searchOptions: SEARCH_OPTIONS });
  index.addAll(jobs.map(toDoc));
  return index;
}

/** No query: everything passes and nothing is highlighted. */
export const NO_HITS = { scores: null, terms: [] };

/**
 * Run `q` against `index`. `scores` maps matching id → BM25 score; `terms` is the union of the
 * indexed terms that matched (after prefix/fuzzy expansion), which is what to highlight.
 */
export function runSearch(index, q) {
  if (!index || !(q || "").trim()) return NO_HITS;
  const scores = new Map();
  const terms = new Set();
  for (const r of index.search(q)) {
    scores.set(r.id, r.score);
    for (const t of r.terms) terms.add(t);
  }
  return { scores, terms: [...terms] };
}
