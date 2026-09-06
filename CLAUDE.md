# CLAUDE.md

wwlocal: a local mirror + browser for WaterlooWorks co-op postings. Python (`uv`), FastAPI viewer, Preact/htm frontend with no build step. See `README.md` for CLI usage and the WaterlooWorks API calls.

## Commands

```sh
uv run wwlocal login | sync | view   # login saves data/cookies.json; sync fills the jobs db; view serves http://127.0.0.1:8765
uv run ruff check src tests && uv run ruff format src tests
uv run pyright
uv run pytest                        # tests/: parse.py derived fields, build_jobs payload
```

## Layout

```
src/wwlocal/
  cli.py            login / sync / view
  config.py         paths and constants (WWLOCAL_DIR moves the data dir)
  waterlooworks.py  HTTP client + action-token scraping
  parse.py          overview HTML and ratings JSON → dicts
  jobs_db.py        waterlooworks_jobs.db schema + the /jobs.json payload
  login.py          playwright login flow
  sync/             the ingester
  viewer/
    app.py          FastAPI app: /, /static, /jobs.json, /api/state, /apply
    state.py        viewer_state.db (SCHEMA + MIGRATIONS)
    static/         index.html, style.css, vendor/preact-htm.mjs, js/
```

## Rules

- `sync/` and `viewer/` never import each other; shared code sits one level up.
- Two databases in `data/` (gitignored): `waterlooworks_jobs.db` is disposable and written only by `sync`; `viewer_state.db` holds user state (`posting_state`) and is written only by `view`. `data/cookies.json` is a session secret.
- Data shaping happens in Python: `jobs_db.build_jobs` attaches `facets`, `comp`, `external_apply`, `comp_text`, `rating_summary` via `parse.py`. The JS only filters, sorts and renders.
- To add a kind of viewer state, add a column in `viewer/state.py` (`SCHEMA` + `MIGRATIONS`); `/api/state` picks it up. Unknown keys → 400.
- Frontend modules: `store.js` (single state object, all actions, only caller of `api.js`), `query.js` (pure facets/filters/sorts, no DOM), `api.js`/`prefs.js` (server / localStorage), `sanitize.js`/`format.js`, `keys.js` (keyboard map), `components/` (pure functions of props). `main.js` re-renders the whole tree on every store change. The only `dangerouslySetInnerHTML` is the posting body in `Detail.js`.
