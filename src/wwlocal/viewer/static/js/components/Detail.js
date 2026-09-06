import { html, useEffect, useRef } from "../../vendor/preact-htm.mjs";
import * as store from "../store.js";
import { COMP_UNIT_LABEL, DATE_TIME, compHourly, compLabel, fmtDate, humanize } from "../format.js";
import { isEmptyHtml, sanitize } from "../sanitize.js";
import { Ratings } from "./Ratings.js";

// Which posting fields become body sections, in what order, with what heading. Anything in
// `fields` not listed here is appended with a humanized heading; SKIP is what the header already shows.
const LABELS = {
  job_summary: "Summary", job_responsibilities: "Responsibilities", required_skills: "Required skills",
  compensation_and_benefits: "Compensation and benefits", additional_employment_arrangement_location_information: "Work arrangement details",
  special_job_requirements: "Special requirements", special_work_term_start_end_date_considerations: "Start and end dates",
  transportation_and_housing: "Transportation and housing", additional_application_information: "How to apply",
  application_documents_required: "Documents required", targeted_degrees_and_disciplines: "Targeted disciplines",
  additional_information: "Additional information", employer_internal_job_number: "Employer job number",
  job_location_if_exact_address_unknown_or_multiple_locations: "Location notes", application_method: "Application method",
};
const BODY_ORDER = ["job_summary", "job_responsibilities", "required_skills", "compensation_and_benefits",
  "additional_employment_arrangement_location_information", "special_work_term_start_end_date_considerations", "special_job_requirements",
  "transportation_and_housing", "additional_information", "additional_application_information", "application_documents_required",
  "application_method", "targeted_degrees_and_disciplines", "job_location_if_exact_address_unknown_or_multiple_locations", "employer_internal_job_number"];
const SHORT = new Set(["application_documents_required", "application_method", "targeted_degrees_and_disciplines", "employer_internal_job_number"]);
const SKIP = new Set(["work_term", "job_type", "job_title", "number_of_job_openings", "level", "region", "job_address_line_one", "job_address_line_two",
  "job_city", "job_province_state", "job_postal_zip_code", "job_country", "employment_location_arrangement", "work_term_duration", "application_deadline", "organization", "division"]);

export function Detail({ state }) {
  const box = useRef();
  useEffect(() => { if (box.current) box.current.scrollTop = 0; }, [state.selectedId]);
  const j = state.jobs.find(x => x.id === state.selectedId);
  return html`
    <div class="detail" ref=${box}>
      ${j ? html`<${Posting} job=${j} mark=${state.marks[j.id] || {}} />` : html`<${Placeholder} />`}
    </div>`;
}

function Placeholder() {
  return html`
    <div class="placeholder">
      <p>Pick a posting on the left.</p>
      <p><kbd>j</kbd> <kbd>k</kbd> move, <kbd>s</kbd> shortlist, <kbd>x</kbd> hide (<kbd>ctrl</kbd>+<kbd>z</kbd> undo), <kbd>a</kbd> mark applied,
        <kbd>v</kbd> toggle viewed, <kbd>o</kbd> open on WaterlooWorks, <kbd>e</kbd> open the employer's own application, <kbd>/</kbd> search.</p>
    </div>`;
}

function Posting({ job: j, mark: m }) {
  const d = j.detail || {}, f = j.facets;
  const place = [j.city, d.region, f.country !== "Canada" && f.country !== "unspecified" ? f.country : ""].filter(Boolean).join(", ");
  const hint = [j.status, j.flags && j.flags.viewed ? "viewed" : "", j.closed_at ? "closed " + fmtDate(j.closed_at) : ""].filter(Boolean).join(", ");
  const docs = f.docs.filter(x => x !== "Cover Letter").map(x => x.replace("University of Waterloo Co-op Work History", "work history")).join(", ").toLowerCase();
  return html`
    <div class="inner">
      <p class="org">${j.organization}${j.division ? html`<span class="div">${j.division}</span>` : null}</p>
      <div class="dh">
        <h2>${j.title}</h2>
        <span class="loc">
          ${place ? html`<span class="place">${place}</span>` : html`<span class="unk">Location unspecified</span>`}
          <span class="arr">${f.arrangement}</span>
        </span>
      </div>
      <div class="facts">
        <${CompCell} job=${j} />
        <div><b>${d.work_term_duration || "—"}</b>${d.work_term || ""}${d.job_type && d.job_type !== "Co-op Main" ? ", " + d.job_type : ""}</div>
        <div><b>${f.docs.includes("Cover Letter") ? "Cover letter" : "No cover letter"}</b>${docs}</div>
        <${ExternalCell} e=${j.external_apply} />
      </div>
      <div class="actions">
        <button class=${"btn star" + (m.star ? " on" : "")} onClick=${() => store.toggleMark(j.id, "star")}>${m.star ? "★ Shortlisted" : "☆ Shortlist"}</button>
        <button class=${"btn" + (m.applied ? " on" : "")} onClick=${() => store.toggleMark(j.id, "applied")}>${m.applied ? "✓ Applied" : "Mark applied"}</button>
        <button class=${"btn" + (m.hidden ? " on" : "")} onClick=${() => store.toggleMark(j.id, "hidden")}>${m.hidden ? "Hidden" : "Hide"}</button>
        <button class=${"btn" + (m.viewed ? "" : " on")} onClick=${() => store.toggleMark(j.id, "viewed")}
          title="Selecting a posting marks it viewed; toggle to put it back in New">${m.viewed ? "Mark unviewed" : "New"}</button>
        <a class="btn primary" href=${"/apply/" + j.id} target="_blank" rel="noopener" title=${"Open posting " + j.id + " on WaterlooWorks (uses the wwlocal session)"}>Apply on WW ↗</a>
        <${ExternalButton} e=${j.external_apply} />
        <span class="hint">${hint}</span>
      </div>
      <${Ratings} job=${j} r=${j.rating_summary} />
      <div class="body">
        <${Body} job=${j} />
        <${Address} job=${j} />
      </div>
      <div class="stamp">
        First seen ${fmtDate(j.first_seen, DATE_TIME)}, last seen ${fmtDate(j.last_seen, DATE_TIME)}${j.div_id ? ", employer division " + j.div_id : ""}
      </div>
    </div>`;
}

/** The "also apply on the employer's site" warning: link, email, or just the fact of it. */
function ExternalCell({ e }) {
  if (!e) return null;
  const where = e.url ? hostOf(e.url) : e.email ? e.email : "see How to apply below";
  return html`<div class="warn ext"><b>Also apply externally</b>${where}</div>`;
}

function ExternalButton({ e }) {
  if (!e) return null;
  if (e.url) return html`<a class="btn primary ext" href=${e.url} target="_blank" rel="noopener noreferrer" title=${e.url}>Apply on ${hostOf(e.url)} ↗</a>`;
  if (e.email) return html`<a class="btn primary ext" href=${"mailto:" + e.email}>Email ${e.email}</a>`;
  return null;
}

function hostOf(url) {
  try { return new URL(url).hostname.replace(/^(www|jobs?|job-boards|boards|careers|apply)\./, ""); } catch { return url; }
}

function CompCell({ job: j }) {
  const c = j.comp, text = j.comp_text;
  if (c) {
    const sub = [COMP_UNIT_LABEL[c.unit] + (c.currency ? " " + c.currency : ""), c.unit !== "hr" ? "≈ $" + Math.round(compHourly(c)) + "/hr" : ""].filter(Boolean).join(", ");
    return html`<div class="pay" title=${text.slice(0, 300)}><b>${compLabel(c)}</b>${sub}</div>`;
  }
  if (text) {
    const short = text.length > 46 ? text.slice(0, 44).replace(/\s+\S*$/, "") + "…" : text;
    return html`<div class="pay" title=${text.slice(0, 300)}><b>Pay not stated</b>${short}</div>`;
  }
  return html`<div class="pay"><b>—</b>no compensation info</div>`;
}

/** One section per non-empty posting field. */
function Body({ job: j }) {
  const f = j.fields || {};
  const keys = [...BODY_ORDER.filter(k => k in f), ...Object.keys(f).filter(k => !SKIP.has(k) && !BODY_ORDER.includes(k))];
  return keys.map(k => {
    const value = k === "application_documents_required" && j.facets.docs.length ? j.facets.docs.join(", ") : f[k];
    const content = fieldContent(value);
    if (!content) return null;
    return html`
      <section class=${"sec" + (SHORT.has(k) ? " short" : "")} key=${k}>
        <h3>${LABELS[k] || humanize(k)}</h3>
        ${content}
      </section>`;
  });
}

/**
 * A field is a string or {text?, html?, list?}. Employer HTML is the one place the page renders
 * markup it didn't build itself, hence the sanitizer and the single dangerouslySetInnerHTML.
 */
function fieldContent(v) {
  if (v == null) return null;
  if (typeof v === "string") return textBlocks(v);
  if (v.html) {
    const clean = sanitize(v.html);
    return isEmptyHtml(clean) ? null : html`<div class="txt" dangerouslySetInnerHTML=${{ __html: clean }}></div>`;
  }
  if (v.list) return v.list.length ? html`<ul class="plain">${v.list.map(x => html`<li key=${x}>${x.replace(/^- Theme - /, "")}</li>`)}</ul>` : null;
  if (v.text) return textBlocks(v.text);
  return null;
}

/** Plain text → paragraphs on blank lines, <br> on single newlines. */
function textBlocks(t) {
  const paras = String(t).split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
  if (!paras.length) return null;
  return html`
    <div class="txt">
      ${paras.map((p, i) => html`<p key=${i}>${p.split("\n").flatMap((line, k) => k ? [html`<br />`, line] : [line])}</p>`)}
    </div>`;
}

function Address({ job: j }) {
  const a = (j.detail || {}).address;
  const addr = a ? [a.line1, a.line2, [a.city, a.province, a.postal_code].filter(Boolean).join(", "), a.country].filter(Boolean).join("\n") : "";
  const locs = j.locations && j.locations.length ? j.locations : [];
  if (!addr && !locs.length) return null;
  return html`
    <section class="sec">
      <h3>Address</h3>
      <div class="addr">${addr}</div>
      ${locs.length && !addr ? html`<div class="locs">${locs.map(l => l.name).join("; ")}</div>` : null}
    </section>`;
}
