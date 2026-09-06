import { html, useEffect } from "../../vendor/preact-htm.mjs";
import * as store from "../store.js";
import { FACETS, FACET_GROUPS, FACET_LABELS, SORTS, facetCounts, facetGroupCounts, passesBase, passesFacets, anyFilterActive } from "../query.js";

const TOGGLES = [["onlyStar", "Shortlist only"], ["showHidden", "Show hidden"], ["hideApplied", "Hide applied"], ["onlyNew", "New only"]];
const SORT_LABELS = {
  "apps-asc": "fewest applicants", "apps-desc": "most applicants", deadline: "deadline", rating: "highest rating",
  hires: "most hires", newest: "newest", org: "employer", title: "title",
};

export function Filters({ state }) {
  useEffect(() => {
    // Click anywhere outside a menu closes the open one.
    const onClick = e => { if (!e.target.closest(".dd")) closeMenus(); };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  const { prefs } = state;
  return html`
    <div class="filters">
      ${Object.keys(FACETS).map(key => html`<${FacetMenu} key=${key} facet=${key} state=${state} />`)}
      <span class="sep"></span>
      ${TOGGLES.map(([name, label]) => html`
        <label class="toggle" key=${name}>
          <input type="checkbox" checked=${!!prefs[name]} onChange=${e => store.setToggle(name, e.target.checked)} /> ${label}
        </label>`)}
      <button class="reset" hidden=${!anyFilterActive(prefs)} onClick=${store.reset}>Clear filters</button>
      <label class="sort">Sort
        <select value=${prefs.sort in SORTS ? prefs.sort : "apps-asc"} onChange=${e => store.setSort(e.target.value)}>
          ${Object.keys(SORTS).map(k => html`<option key=${k} value=${k}>${SORT_LABELS[k]}</option>`)}
        </select>
      </label>
    </div>`;
}

function closeMenus(except) {
  for (const d of document.querySelectorAll("details.dd[open]")) if (d !== except) d.open = false;
}

/** One <details> dropdown. Counts reflect every other filter, so an option shows what picking it would leave. */
function FacetMenu({ facet, state }) {
  const sel = state.prefs.filters[facet] || [];
  const pool = state.jobs.filter(j => passesBase(j, state) && passesFacets(j, state.prefs.filters, facet));
  const option = ([v, n]) => html`
    <label key=${v}>
      <input type="checkbox" checked=${sel.includes(v)} onChange=${e => store.setFilter(facet, v, e.target.checked)} />
      <span>${v}</span><span class="n">${n}</span>
    </label>`;
  const body = FACET_GROUPS[facet]
    ? facetGroupCounts(facet, pool).map(([g, counts, total]) => html`
        <div class="group" key=${g}>
          <${GroupHeader} label=${g} total=${total} values=${counts.map(c => c[0])} sel=${sel} facet=${facet} />
          ${counts.map(option)}
        </div>`)
    : facetCounts(facet, pool).map(option);
  return html`
    <details class=${"dd" + (sel.length ? " active" : "")} onToggle=${e => { if (e.target.open) closeMenus(e.target); }}>
      <summary>${FACET_LABELS[facet]}${sel.length ? html` <span class="count">${sel.length}</span>` : null}</summary>
      <div class="menu">
        ${body}
        ${sel.length ? html`<button class="clear" type="button" onClick=${() => store.clearFilter(facet)}>Clear</button>` : null}
      </div>
    </details>`;
}

/** A group's header row: ticking it selects every option under it; half-ticked when only some are. */
function GroupHeader({ label, total, values, sel, facet }) {
  const picked = values.filter(v => sel.includes(v)).length;
  const all = picked === values.length;
  return html`
    <label class="group-head">
      <input type="checkbox" checked=${all} ref=${el => { if (el) el.indeterminate = picked > 0 && !all; }}
        onChange=${e => store.setFilterMany(facet, values, e.target.checked)} />
      <span>${label}</span><span class="n">${total}</span>
    </label>`;
}
