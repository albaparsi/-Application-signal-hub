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
3. Company/role/URL are pre-filled with a best-effort guess (page `<h1>`,
   `og:site_name`/hostname) — this is generic, not site-specific, so check
   it before saving.
4. Fix anything wrong, set a status if it's not just "saved", and click
   **Save application**.

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
