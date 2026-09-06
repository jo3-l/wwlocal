import { html } from "../../vendor/preact-htm.mjs";
import { ALL_AVG_FALLBACK, ratingClass, termLabel } from "../format.js";

/** The collapsible "Hiring history and ratings" panel under the posting header. */
export function Ratings({ job, r }) {
  const hasAny = r.org_hires.length || r.rating != null || r.programs;
  if (!hasAny) {
    return html`
      <details class="ratings">
        <summary>Hiring history and ratings <span class="sub">none on WaterlooWorks</span></summary>
        <div class="grid"><p class="none">WaterlooWorks has no hiring report for this employer division.</p></div>
      </details>`;
  }
  const brief = [r.hires_total ? `${r.hires_total} hired over ${r.terms.length} terms` : "", r.rating != null ? `rated ${r.rating.toFixed(1)}` : ""].filter(Boolean).join(", ");
  return html`
    <details class="ratings">
      <summary>Hiring history and ratings${brief ? html` <span class="sub">${brief}</span>` : null}</summary>
      <div class="grid">
        <div><${Hist} r=${r} /></div>
        <div><${Satisfaction} r=${r} /></div>
        ${r.questions ? html`<div><${Questions} job=${job} r=${r} /></div>` : null}
        ${r.programs && r.programs.length ? html`<div><div class="hist-div" style="margin:0 0 8px">Programs most often hired</div><${Programs} r=${r} /></div>` : null}
      </div>
    </details>`;
}

function Hist({ r }) {
  if (!r.org_hires.length) return html`<p class="none">No hires recorded.</p>`;
  const max = Math.max(1, ...r.org_hires);
  const sameRows = r.div_hires.length && r.div_hires.join() === r.org_hires.join();
  const divTotal = r.div_hires.reduce((a, b) => a + b, 0);
  return html`
    <div class="hist">
      ${r.org_hires.map((v, i) => html`
        <div class="col" key=${i} title=${r.terms[i] + ": " + v}>
          <span class="v">${v || ""}</span>
          ${v ? html`<i style=${{ height: Math.max(4, Math.round(v / max * 56)) + "px" }}></i>` : html`<i class="z"></i>`}
          <span class="l">${termLabel(r.terms[i])}</span>
        </div>`)}
    </div>
    ${r.div_hires.length && !sameRows ? html`<div class="hist-div">This division: ${divTotal} of the ${r.hires_total} hires (${r.div_hires.join(" ")})</div>` : null}`;
}

function Satisfaction({ r }) {
  if (r.rating == null) return html`<p class="none">No work term ratings yet.</p>`;
  const avg = r.all_avg ?? ALL_AVG_FALLBACK;
  const dmax = r.dist ? Math.max(1, ...r.dist.map(x => x[1])) : 1;
  return html`
    <div class="hero">
      <span class="n">${r.rating.toFixed(1)}</span>
      <span class="of">of 10, from ${r.rating_n} rating${r.rating_n === 1 ? "" : "s"}</span>
      <span class=${"cmp " + ratingClass(r.rating, r.all_avg)}>all co-op students <b>${avg.toFixed(1)}</b></span>
    </div>
    ${r.div_rating != null && r.div_rating !== r.rating ? html`<div class="hist-div">This division ${r.div_rating.toFixed(1)} from ${r.div_n}</div>` : null}
    ${r.dist ? html`
      <div class="dist">
        ${r.dist.map(([k, v]) => html`
          <div class="col" key=${k} title=${v + "% rated " + k}>
            ${v ? html`<i style=${{ height: Math.max(3, Math.round(v / dmax * 40)) + "px" }}></i>` : html`<i class="z"></i>`}
            <span class="l">${k}</span>
          </div>`)}
      </div>` : null}`;
}

function Questions({ job, r }) {
  const pct = v => (v / 5 * 100).toFixed(1) + "%";
  return html`
    <div class="qs">
      ${r.questions.map(([q, e, a]) => html`
        <div class="q" key=${q} title=${q}>${q.replace(/^Q\d+\.\s*/, "").replace(/\s*\(.*\)$/, "")}</div>
        <div class="n">${e.toFixed(1)}</div>
        <div class="bar" title=${q + ": " + e + " vs " + a + " for all students"}>
          <i style=${{ width: pct(e) }}></i>${a != null ? html`<em style=${{ left: pct(a) }}></em>` : null}
        </div>`)}
    </div>
    <div class="legend">
      <span><i></i>${job.organization}</span><span><em></em>all co-op students</span>
      <span>scale 1–5${r.questions_range ? ", " + r.questions_range : ""}</span>
    </div>`;
}

function Programs({ r }) {
  const pmax = Math.max(1, ...r.programs.map(x => x[1]));
  return html`
    <div class="progs">
      ${r.programs.slice(0, 8).map(([p, v]) => html`
        <div class="p" key=${p} title=${p}>${p}</div>
        <div class="bar"><i style=${{ width: (v / pmax * 100).toFixed(1) + "%" }}></i></div>
        <div class="v">${v}</div>`)}
    </div>`;
}
