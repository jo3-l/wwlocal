import { html } from "../../vendor/preact-htm.mjs";
import * as store from "../store.js";
import { relTime } from "../format.js";

export function TopBar({ state }) {
  return html`
    <header class="top">
      <h1>WaterlooWorks postings</h1>
      <${Meta} state=${state} />
      <div class="spacer"></div>
      <input class="search" id="search" type="search" placeholder="Search title, employer, skills"
        autocomplete="off" value=${state.prefs.q} onInput=${e => store.setQuery(e.target.value)} />
    </header>`;
}

function Meta({ state }) {
  if (state.error) return html`<div class="meta">${state.error}</div>`;
  if (!state.loaded) return html`<div class="meta">loading…</div>`;
  const { jobs, generatedAt } = state;
  const terms = [...new Set(jobs.map(j => (j.detail || {}).work_term).filter(Boolean))];
  const closed = jobs.filter(j => j.closed_at).length;
  return html`
    <div class="meta" title=${generatedAt}>
      <b>${jobs.length}</b> postings${terms.length === 1 ? ", " + terms[0] : ""}${closed ? `, ${closed} closed` : ""}, synced ${relTime(generatedAt)}
    </div>`;
}
