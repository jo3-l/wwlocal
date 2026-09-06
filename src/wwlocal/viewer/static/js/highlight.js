// Highlights the search words wherever they appear in the rendered page, via the CSS Custom
// Highlight API. It paints Ranges over existing text nodes, so nothing in the Preact tree (or
// the employer HTML in Detail.js) is touched; browsers without the API simply get no highlight.

import { searchWords } from "./query.js";

const NAME = "search";

export function highlightMatches(root, q) {
  if (typeof Highlight === "undefined" || !CSS.highlights) return;
  const words = searchWords(q);
  if (!root || !words.length) { CSS.highlights.delete(NAME); return; }
  const ranges = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.data.toLowerCase();
    for (const w of words) {
      for (let i = text.indexOf(w); i >= 0; i = text.indexOf(w, i + w.length)) {
        const r = new Range();
        r.setStart(node, i);
        r.setEnd(node, i + w.length);
        ranges.push(r);
      }
    }
  }
  CSS.highlights.set(NAME, new Highlight(...ranges));
}
