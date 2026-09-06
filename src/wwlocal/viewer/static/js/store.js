// The one place state changes. Components read `get()` and call the exported actions; every
// action ends by notifying subscribers, and main.js re-renders the whole tree from the new state.

import * as api from "./api.js";
import { loadPrefs, savePrefs } from "./prefs.js";
import { searchText, visibleJobs } from "./query.js";

let state = {
  loaded: false,
  error: null,        // shown in the top bar instead of the meta line
  jobs: [],
  generatedAt: null,
  marks: {},          // id → {star, hidden, applied, viewed}; only non-default values are present
  prefs: loadPrefs(),
  selectedId: null,
  hay: new Map(),     // id → searchText(job), built once per load
};
const hideUndo = [];  // ids hidden this session, most recent last (ctrl+z)
const listeners = new Set();
let visCache = { state: null, list: [] };

export const get = () => state;
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

function set(patch) {
  state = { ...state, ...patch };
  for (const fn of listeners) fn(state);
}

export const mark = id => state.marks[id] || {};

/** Filtered + sorted list for the current state (memoised on state identity). */
export function visible() {
  if (visCache.state !== state) visCache = { state, list: visibleJobs(state) };
  return visCache.list;
}

// ---------------------------------------------------------------- loading

export async function boot() {
  let data, marks;
  try {
    [data, marks] = await Promise.all([api.loadJobs(), api.loadMarks()]);
  } catch (err) {
    set({ error: "could not load jobs.json (" + err.message + "). Run `uv run wwlocal view`, not file://." });
    return;
  }
  const hay = new Map(data.jobs.map(j => [j.id, searchText(j)]));
  set({ loaded: true, jobs: data.jobs, generatedAt: data.generated_at, marks, hay });
}

// ---------------------------------------------------------------- marks

/** Optimistic: apply locally, then persist. On failure reload from the server so the UI matches disk. */
function setMark(id, patch) {
  const next = { ...mark(id), ...patch };
  const marks = { ...state.marks };
  if (next.star || next.hidden || next.applied || next.viewed) marks[id] = next; else delete marks[id];
  set({ marks });
  api.patchMark(id, patch)
    .then(m => {
      const marks = { ...state.marks };
      if (Object.keys(m).length) marks[id] = m; else delete marks[id];
      set({ marks });
    })
    .catch(async err => {
      console.error("mark not saved:", err);
      let marks = state.marks;
      try { marks = await api.loadMarks(); } catch { /* keep what we have */ }
      set({ marks, error: "could not save mark (" + err.message + ")" });
    });
}

export function toggleMark(id, key) {
  const was = !!mark(id)[key];
  if (key === "hidden" && !was) hideUndo.push(id);
  const before = visible();
  const idx = before.findIndex(j => j.id === id);
  setMark(id, { [key]: !was });
  // If the posting just dropped out of the list, move the cursor to its neighbour.
  const gone = (key === "hidden" && !was && !state.prefs.showHidden) || (key === "viewed" && !was && state.prefs.onlyNew);
  if (gone && id === state.selectedId) {
    const rest = visible().filter(j => j.id !== id);
    if (rest.length) select(rest[Math.min(idx, rest.length - 1)].id);
  }
}

export function undoHide() {
  let id;
  while (hideUndo.length && !mark(id = hideUndo.pop()).hidden) id = null;
  if (!id) return;
  setMark(id, { hidden: false });
  select(id);
}

// ---------------------------------------------------------------- selection

export function select(id) {
  if (id != null && !state.jobs.some(j => j.id === id)) return;
  set({ selectedId: id });
  const hash = id ? "#" + id : "";
  if (location.hash !== hash) history.replaceState(null, "", location.pathname + location.search + hash);
  if (id && !mark(id).viewed) setMark(id, { viewed: true });
}

export function move(delta) {
  const list = visible();
  if (!list.length) return;
  const i = list.findIndex(j => j.id === state.selectedId);
  const n = i < 0 ? 0 : Math.max(0, Math.min(list.length - 1, i + delta));
  select(list[n].id);
}

// ---------------------------------------------------------------- prefs

function setPrefs(patch) {
  const prefs = { ...state.prefs, ...patch };
  savePrefs(prefs);
  set({ prefs });
}
export const setQuery = q => setPrefs({ q });
export const setSort = sort => setPrefs({ sort });
export const setToggle = (name, on) => setPrefs({ [name]: !!on });
export function setFilter(key, value, on) {
  const sel = new Set(state.prefs.filters[key] || []);
  on ? sel.add(value) : sel.delete(value);
  setPrefs({ filters: { ...state.prefs.filters, [key]: [...sel] } });
}
/** Tick or untick several options of one menu at once (a group header). */
export function setFilterMany(key, values, on) {
  const sel = new Set(state.prefs.filters[key] || []);
  for (const v of values) on ? sel.add(v) : sel.delete(v);
  setPrefs({ filters: { ...state.prefs.filters, [key]: [...sel] } });
}
export const clearFilter = key => setPrefs({ filters: { ...state.prefs.filters, [key]: [] } });
export const reset = () => setPrefs({ filters: {}, q: "", onlyStar: false, hideApplied: false, onlyNew: false });
