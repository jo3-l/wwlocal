// Sort, filters and search live in localStorage; marks (star/hidden/…) live on the server via api.js.

import { FACETS } from "./query.js";

const KEY = "wwview:prefs";

export const DEFAULT_PREFS = {
  sort: "apps-asc", filters: {}, q: "",
  onlyStar: false, showHidden: false, hideApplied: false, onlyNew: false,
};

export function loadPrefs() {
  let prefs;
  try { prefs = { ...DEFAULT_PREFS, ...(JSON.parse(localStorage.getItem(KEY)) ?? {}) }; }
  catch { return { ...DEFAULT_PREFS }; }
  // Drop filters for menus that no longer exist (e.g. the old separate Region/Country menus).
  prefs.filters = Object.fromEntries(Object.entries(prefs.filters || {}).filter(([k]) => FACETS[k]));
  return prefs;
}

export function savePrefs(prefs) {
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* private mode etc. */ }
}
