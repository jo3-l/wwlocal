// Posting bodies arrive as employer-authored HTML. This is the only HTML the page renders raw
// (see Detail.js), so everything active is stripped and the markup is tidied for display.

export function sanitize(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  for (const el of doc.querySelectorAll("script,style,iframe,object,embed,link,meta,form,input,button")) el.remove();
  for (const el of doc.body.querySelectorAll("*")) {
    for (const a of [...el.attributes]) {
      const n = a.name.toLowerCase();
      if (n.startsWith("on") || n === "style" || n === "class" || n === "id") el.removeAttribute(a.name);
      else if ((n === "href" || n === "src") && /^\s*(javascript|data):/i.test(a.value)) el.removeAttribute(a.name);
    }
    if (el.tagName === "A") { el.setAttribute("target", "_blank"); el.setAttribute("rel", "noopener"); }
    if (el.tagName === "IMG") el.remove();
  }
  // Collapse runs of <br> (whitespace between them allowed) into one paragraph gap.
  for (const br of [...doc.body.querySelectorAll("br")]) {
    if (!br.parentNode) continue;
    let n = br.nextSibling;
    const run = [];
    while (n && ((n.nodeType === 3 && !n.textContent.trim()) || (n.nodeType === 1 && n.tagName === "BR"))) { run.push(n); n = n.nextSibling; }
    if (run.some(x => x.nodeType === 1)) {
      for (const x of run) x.remove();
      br.replaceWith(Object.assign(doc.createElement("span"), { className: "gap" }));
    }
  }
  // Trailing breaks inside a block add nothing.
  for (const el of doc.body.querySelectorAll("p,li,div")) {
    while (el.lastChild && isBlank(el.lastChild)) el.lastChild.remove();
  }
  return doc.body.innerHTML;
}

function isBlank(node) {
  if (node.nodeType === 3) return !node.textContent.trim();
  return node.nodeType === 1 && (node.tagName === "BR" || (node.tagName === "SPAN" && node.className === "gap"));
}

/** True when the sanitized HTML has no visible text. */
export function isEmptyHtml(html) {
  return !html.replace(/<[^>]+>/g, "").trim();
}
