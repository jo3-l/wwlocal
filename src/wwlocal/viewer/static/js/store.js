// The one place state changes. Components read `get()` and call the exported actions; every
// action ends by notifying subscribers, and main.js re-renders the whole tree from the new state.

import * as api from "./api.js";
import { loadPrefs, savePrefs } from "./prefs.js";
import { DEFAULT_SORT, visibleJobs } from "./query.js";
import { NO_HITS, buildIndex, runSearch } from "./search.js";

let state = {
  loaded: false,
  error: null,        // shown in the top bar instead of the meta line
  jobs: [],
  generatedAt: null,
  marks: {},          // id → {star, hidden, applied, viewed}; only non-default values are present
  prefs: loadPrefs(),
  selectedId: null,
  index: null,        // search.js index over `jobs`; built on the first query (see ensureIndex)
  hits: NO_HITS,      // runSearch(index, prefs.q): {scores, terms}; scores is null when there's no query or no index yet
  sortBeforeSearch: null,  // the sort to restore when the query is cleared (see setQuery)
};
const undoStack = [];  // {id, key, was}: each explicit mark change this session, most recent last (ctrl+z)
const redoStack = [];  // entries undone, cleared by the next new change (ctrl+shift+z)
let indexing = null;  // the in-flight buildIndex(), so a burst of keystrokes builds it once
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
  set({ loaded: true, jobs: data.jobs, generatedAt: data.generated_at, marks });
  if (state.prefs.q.trim()) ensureIndex();
}

/**
 * Build the search index on first use. Until it's ready a query matches everything; the list
 * narrows when the build resolves (≈100ms, only ever once), against whatever the query is by then.
 */
function ensureIndex() {
  if (state.index || indexing) return;
  indexing = buildIndex(state.jobs).then(index => {
    indexing = null;
    set({ index, hits: runSearch(index, state.prefs.q) });
  }, err => {
    indexing = null;
    set({ error: "search index failed to build (" + err.message + ")" });
  });
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

/** Apply one mark and, if the selected posting just dropped out of the list, move the cursor to its neighbour. */
function applyMark(id, key, value) {
  const idx = visible().findIndex(j => j.id === id);
  setMark(id, { [key]: value });
  if (id === state.selectedId && !visible().some(j => j.id === id)) {
    const rest = visible();
    if (rest.length) select(rest[Math.min(Math.max(idx, 0), rest.length - 1)].id);
  }
}

export function toggleMark(id, key) {
  const was = !!mark(id)[key];
  undoStack.push({ id, key, was });
  redoStack.length = 0;
  applyMark(id, key, !was);
}

// Only explicit toggles are undoable; the `viewed` that select() applies goes straight to setMark.
export const undo = () => shift(undoStack, redoStack);
export const redo = () => shift(redoStack, undoStack);

function shift(from, to) {
  let e;
  while ((e = from.pop()) && !!mark(e.id)[e.key] === e.was) e = null;  // already reverted by hand
  if (!e) return;
  to.push({ ...e, was: !e.was });
  applyMark(e.id, e.key, e.was);
  select(e.id);
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
/** Typing a query switches to relevance order; clearing it puts the previous sort back. */
export function setQuery(q) {
  const had = !!state.prefs.q.trim(), has = !!q.trim();
  let { sort } = state.prefs, { sortBeforeSearch } = state;
  if (has && !had && sort !== "relevance") { sortBeforeSearch = sort; sort = "relevance"; }
  if (!has && had && sort === "relevance") { sort = sortBeforeSearch || DEFAULT_SORT; sortBeforeSearch = null; }
  state = { ...state, sortBeforeSearch, hits: runSearch(state.index, q) };
  setPrefs({ q, sort });
  if (has) ensureIndex();
}
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
export function reset() {
  setQuery("");
  setPrefs({ filters: {}, onlyStar: false, hideApplied: false, onlyNew: false });
}
