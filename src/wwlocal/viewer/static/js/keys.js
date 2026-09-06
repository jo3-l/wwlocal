// Keyboard map. Everything routes to store actions; the only DOM it touches is menus and the search box.

import * as store from "./store.js";

function closeMenus() {
  for (const d of document.querySelectorAll("details.dd[open]")) d.open = false;
}

export function bindKeys() {
  document.addEventListener("keydown", e => {
    const tag = (e.target.tagName || "").toLowerCase();
    if (e.key === "Escape") { e.target.blur(); closeMenus(); return; }
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "z") { e.preventDefault(); store.undoHide(); return; }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const id = store.get().selectedId;
    switch (e.key) {
      case "j": case "ArrowDown": e.preventDefault(); store.move(1); break;
      case "k": case "ArrowUp": e.preventDefault(); store.move(-1); break;
      case "s": if (id) store.toggleMark(id, "star"); break;
      case "x": if (id) store.toggleMark(id, "hidden"); break;
      case "a": if (id) store.toggleMark(id, "applied"); break;
      case "v": if (id) store.toggleMark(id, "viewed"); break;
      case "o": if (id) window.open(`/apply/${id}`, "_blank", "noopener"); break;
      case "e": {
        const e2 = id && (store.get().jobs.find(j => j.id === id) || {}).external_apply;
        if (e2 && e2.url) window.open(e2.url, "_blank", "noopener,noreferrer");
        else if (e2 && e2.email) window.location.href = "mailto:" + e2.email;
        break;
      }
      case "/": {
        e.preventDefault();
        const box = document.getElementById("search");
        if (box) { box.focus(); box.select(); }
        break;
      }
    }
  });
}
