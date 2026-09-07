import { html, useEffect, useRef } from "../../vendor/preact-htm.mjs";
import * as store from "../store.js";
import { ratingClass } from "../format.js";

export function List({ state, visible }) {
  const box = useRef();
  useEffect(() => {
    const el = box.current && box.current.querySelector(".row.sel");
    if (el) el.scrollIntoView({ block: "nearest" });
  }, [state.selectedId]);

  const { jobs, marks, selectedId } = state;
  const stars = jobs.filter(j => (marks[j.id] || {}).star).length;
  const fresh = jobs.filter(j => !(marks[j.id] || {}).viewed).length;
  const side = [fresh ? fresh + " new" : "", stars ? stars + " shortlisted" : ""].filter(Boolean).join(", ");
  return html`
    <div class="list" ref=${box}>
      <div class="list-head"><span>${visible.length} of ${jobs.length} postings</span><span>${side}</span></div>
      ${state.loaded && !visible.length ? html`<div class="empty">Nothing matches. Loosen a filter or clear the search.</div>` : null}
      ${visible.map(j => html`<${Row} key=${j.id} job=${j} mark=${marks[j.id] || {}} selected=${j.id === selectedId} />`)}
    </div>`;
}

function Row({ job: j, mark: m, selected }) {
  const cls = ["row", selected ? "sel" : "", m.star ? "star" : "", m.applied ? "applied" : "", m.hidden ? "hidden-mark" : ""].filter(Boolean).join(" ");
  const f = j.facets;
  const meta = [f.arrangement, j.city || f.region, f.duration === "4 months" ? "" : f.duration, j.closed_at ? "closed" : ""].filter(Boolean);
  return html`
    <div class=${cls} tabindex="-1" onClick=${() => store.select(j.id)}>
      <div class="o">
        ${m.star ? html`<span class="starmark" title="Shortlisted">★</span>` : null}${j.organization}${j.external_apply ? html`<span class="ext" title="Employer also wants an application on their own site">+ external</span>` : null}${m.viewed ? null : html`<span class="new">new</span>`}
      </div>
      <div class="t">${j.title}</div>
      <div class="m"><span class="arr">${meta[0]}</span>${meta.slice(1).map(x => html`<span key=${x}>${x}</span>`)}</div>
      <div class="right">
        <span class="apps"><b>${j.application_count}</b> ${j.application_count === 1 ? "applicant" : "applicants"}</span>
        <${Spark} r=${j.rating_summary} />
        <${RateLine} r=${j.rating_summary} />
      </div>
    </div>`;
}

function Spark({ r }) {
  if (!r.org_hires.length) return html`<span class="spark none">no hiring history</span>`;
  const max = Math.max(1, ...r.org_hires);
  const title = "Students hired per term: " + r.terms.map((t, i) => t + " " + r.org_hires[i]).join(", ");
  return html`
    <span class="spark" title=${title}>
      ${r.org_hires.map((v, i) => v ? html`<i key=${i} style=${{ height: Math.max(3, Math.round(v / max * 16)) + "px" }}></i>` : html`<i key=${i} class="z"></i>`)}
    </span>`;
}

function RateLine({ r }) {
  if (r.rating == null) return html`<span class="rate">${r.hires_total ? r.hires_total + " hired, unrated" : ""}</span>`;
  const avg = r.all_avg ?? 8.5;
  return html`
    <span class=${"rate " + ratingClass(r.rating, r.all_avg)} title=${"Average work term satisfaction vs " + avg + " for all co-op students"}>
      <b>${r.rating.toFixed(1)}</b> from ${r.rating_n}
    </span>`;
}
