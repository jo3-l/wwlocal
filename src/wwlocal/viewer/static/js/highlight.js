// Highlights painted via the CSS Custom Highlight API: the matched search terms wherever they
// appear in the page, and the programming languages a posting names within its body. Both paint Ranges
// over existing text nodes, so nothing in the Preact tree (or the employer HTML in Detail.js) is
// touched; browsers without the API simply get no highlight.

const ok = () => typeof Highlight !== "undefined" && !!CSS.highlights;

/** `terms` are the index terms that matched (search.js), so "learn" highlights "learning". */
export function highlightMatches(root, terms) {
  paint("search", root, terms.map(t => t.toLowerCase()), { fold: true });
}

/**
 * `forms` are the exact strings languages.py matched in this posting ("Golang", "Go"), painted
 * case-sensitively and only at word boundaries so "C" doesn't light up every capital C.
 */
export function highlightLanguages(root, forms) {
  paint("language", root, forms, { fold: false, whole: true });
}

const WORD = /[A-Za-z0-9+#]/;

function paint(name, root, needles, { fold, whole }) {
  if (!ok()) return;
  if (!root || !needles.length) { CSS.highlights.delete(name); return; }
  const ranges = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = fold ? node.data.toLowerCase() : node.data;
    for (const w of needles) {
      for (let i = text.indexOf(w); i >= 0; i = text.indexOf(w, i + w.length)) {
        const end = i + w.length;
        if (whole && ((i > 0 && WORD.test(text[i - 1])) || (end < text.length && /[A-Za-z+#]/.test(text[end])))) continue;
        const r = new Range();
        r.setStart(node, i);
        r.setEnd(node, end);
        ranges.push(r);
      }
    }
  }
  CSS.highlights.set(name, new Highlight(...ranges));
}
