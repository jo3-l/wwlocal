import { h, render } from "../vendor/preact-htm.mjs";
import * as store from "./store.js";
import { bindKeys } from "./keys.js";
import { App } from "./components/App.js";
import { highlightMatches } from "./highlight.js";

const root = document.getElementById("app");
const draw = state => {
  render(h(App, { state, visible: store.visible() }), root);
  highlightMatches(root.querySelector(".split"), state.hits.terms);
};

store.subscribe(draw);
draw(store.get());
bindKeys();

window.addEventListener("hashchange", () => {
  const id = +location.hash.slice(1);
  if (id && id !== store.get().selectedId) store.select(id);
});

store.boot().then(() => {
  const id = +location.hash.slice(1);
  if (id) store.select(id);
});
