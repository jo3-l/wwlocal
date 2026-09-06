// The only place the page talks to the server. Relative URLs, so the viewer works under any prefix.

async function json(res) {
  if (!res.ok) throw new Error(res.status + " " + res.statusText);
  return res.json();
}

export const loadJobs = () => fetch("jobs.json", { cache: "no-store" }).then(json);
export const loadMarks = () => fetch("api/state", { cache: "no-store" }).then(json);
export const patchMark = (id, patch) =>
  fetch("api/state/" + id, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then(json);
