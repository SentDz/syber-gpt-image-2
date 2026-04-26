# CyberGen Image Site

React frontend plus a FastAPI backend for Sub2API/OpenAI-compatible image generation.

Local services detected on this machine:

- Sub2API: `http://127.0.0.1:9878`, OpenAI-compatible base URL `http://127.0.0.1:9878/v1`

The app calls `/v1/images/generations` for generation, `/v1/images/edits` for edits, and reads balance/usage from `/v1/usage`. Per generation, the frontend lets users choose a scale such as `2K` and an aspect ratio such as `16:9`, then sends the concrete provider `size` as `WIDTHxHEIGHT` such as `2048x1152`. Scale buckets are based on the longest edge: `1K` stays at or below 1024px, `2K` at or below 2048px, and `4K` at or below 3840px. `4K + 1:1` is disabled because `3840x3840` exceeds the upstream pixel budget; direct square sizes above `2048x2048` are rejected by the backend. Use `2K + 1:1` for square images.

Identity modes:

- Guests get a local cookie-backed owner id. Their history and config are isolated per browser.
- Registered users sign in against your deployed `sub2api` instance through this site's FastAPI backend.
- After login, the backend resolves or creates a per-user Sub2API API key and binds it to that signed-in owner.
- Guest history is merged into the user after successful login/register.

The inspiration feed syncs GPT-Image-2 cases from:

```text
https://github.com/EvoLinkAI/awesome-gpt-image-2-prompts/blob/main/README.md
```

By default the backend parses the README on startup and refreshes it every 6 hours.

## Run

```bash
npm install
python3 -m pip install -r backend/requirements.txt
npm run backend
npm run dev
```

Open `http://127.0.0.1:3000`, then save your Sub2API key in `API Config`.

For guest mode, save a personal Sub2API API key in `API Config`.

For account mode, use `Register` or `Login`. The backend talks to Sub2API auth endpoints and manages the API key automatically.

## Backend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Important endpoints:

- `GET /api/auth/public-settings`
- `GET /api/auth/session`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/login/2fa`
- `POST /api/auth/logout`
- `GET /api/account`
- `GET /api/balance`
- `GET /api/history`
- `POST /api/images/generate`
- `POST /api/images/edit`
- `PUT /api/config`
- `GET /api/inspirations`
- `POST /api/inspirations/sync`

Generated image files are stored under `backend/storage/images`; uploaded edit references are stored under `backend/storage/uploads`.

Owner config, history, ledger entries, and local session state are stored in `backend/data/app.sqlite3`.

## Tests

```bash
PYTHONPATH=backend pytest backend/tests
npm run build
```
