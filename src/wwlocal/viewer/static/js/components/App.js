import { html } from "../../vendor/preact-htm.mjs";
import { TopBar } from "./TopBar.js";
import { Filters } from "./Filters.js";
import { List } from "./List.js";
import { Detail } from "./Detail.js";

/** Whole page, a pure function of store state plus the current visible list. */
export function App({ state, visible }) {
  return html`
    <${TopBar} state=${state} />
    <${Filters} state=${state} />
    <div class="split">
      <${List} state=${state} visible=${visible} />
      <${Detail} state=${state} />
    </div>`;
}
