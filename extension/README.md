# Application Signal Hub — browser extension (MVP)

Manual, user-triggered capture: click the toolbar icon on a job posting,
review the extracted preview, edit anything wrong, and confirm to save it.
Nothing is saved without that explicit click.

## Load it (Chrome/Edge/Brave — any Chromium browser)

1. Make sure the API is running: `docker compose up` from the repo root
   (or `uvicorn app.main:app --reload` from `backend/` for a bare-metal
   run — either way it needs to be reachable at `http://localhost:8000`).
2. Go to `chrome://extensions`.
3. Turn on **Developer mode** (top right).
4. Click **Load unpacked** and select this `extension/` folder.
5. Pin the icon (puzzle-piece menu → pin) for easy access.

## Using it

1. Open a job posting page.
2. Click the extension icon.
3. Company/role/location/status/URL are pre-filled by
   `POST /extraction/infer` on the backend, which:
   - Uses an LLM (Claude) when `ANTHROPIC_API_KEY` is set in `.env` — this
     is what infers **status** (e.g. "applied" if the page clearly shows a
     submitted application), which structured data and DOM heuristics
     can't do.
   - Otherwise falls back to the page's `schema.org/JobPosting` structured
     data (`application/ld+json`) if present — most real job boards
     (LinkedIn, Indeed, Greenhouse, Lever, Workday...) embed this for
     Google Jobs SEO, and it's far more reliable than scraping visible
     text (e.g. it's how we get the real hiring company on LinkedIn
     instead of "LinkedIn" itself).
   - If the API can't be reached at all, the popup falls back once more to
     a fully local `<h1>`/`og:site_name`/hostname guess (no status
     inference in that case — defaults to "saved").

   Whichever path fills it in, check it before saving — it's a starting
   point, not guaranteed correct.
4. Fix anything wrong (or leave it — that's the point), add notes if you
   want, and click **Save application**.

## Permissions, and why

- `activeTab` + `scripting`: lets the popup read the page you're currently
  looking at, only when you click the icon — no background access to
  browsing history or other tabs.
- `host_permissions` for `http://localhost:8000/*` only: needed so the
  popup's `fetch` to the API isn't blocked by CORS. This is the app's own
  API, not a third-party host, and is the one narrow exception to
  activeTab-only. When the API moves off localhost, update this (and
  `API_BASE` in `popup.js`) together.

No other host permissions are requested. Extraction on arbitrary sites is
deliberately generic for the same reason — broad DOM scraping tuned per
site is a V2 concern (see root `CLAUDE.md`), not something this MVP reaches
for.
