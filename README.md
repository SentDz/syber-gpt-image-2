# CyberGen Image Site

React frontend plus a FastAPI backend for Sub2API/OpenAI-compatible image generation.

Local services detected on this machine:

- Sub2API: `http://127.0.0.1:9878`, OpenAI-compatible base URL `http://127.0.0.1:9878/v1`

The app calls `/v1/images/generations` for generation, `/v1/images/edits` for edits, and reads balance/usage from `/v1/usage`. Per generation, the frontend lets users choose a scale such as `1K (1080p)` or `2K (1440p)` and an aspect ratio such as `16:9`, then sends the concrete provider `size` as `WIDTHxHEIGHT`. The backend keeps dimensions aligned to the provider requirement that width and height are divisible by 16. For example, `1K + 9:16` uses `1152x2048` because exact `1080x1920` is rejected upstream, while `2K + 9:16` uses standard `1440x2560`. `4K + 1:1` is disabled because square sizes above `2048x2048` exceed the upstream pixel budget.

Local billing ledger entries are written per generated image. Default prices are `IMAGE_PRICE_1K_USD=0.134`, `IMAGE_PRICE_2K_USD=0.201`, and `IMAGE_PRICE_4K_USD=0.268`; set these environment variables to match your JokoAI/Sub2API group pricing.

For signed-in users using the system-managed key, the backend reads recent JokoAI/Sub2API `/api/v1/usage` records and stores the real `actual_cost` when available. Signed-in users who override the key, and guests who manually enter a key, use the local image price estimate and are marked as estimated in the UI.

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
