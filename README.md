# Mini KYC - Digital Onboarding

Full-stack proof of concept for a digital bank: a customer enters an email and uploads a photo of an identity document,
an AI/OCR service extracts the data automatically, and the onboarding record is stored in a relational database
through stored procedures. Built for the Fractal Developer Training Program, challenge **DTP-L3-2026** (Level 3).

| | |
|---|---|
| Live app | https://mini-kyc.onrender.com |
| API docs (Swagger) | https://mini-kyc.onrender.com/docs |
| Stack | React + Vite · Python FastAPI · MySQL 8 (stored procedures) · Google Gemini Flash · Render + Aiven |

## How it works

```
User -> Frontend -> API -> AI/OCR service -> Database
        upload      validate   extract fields   store via stored procedure
```

1. The React UI validates the email and the file (JPG/PNG, max 5 MB) and sends `multipart/form-data`.
2. The API validates the image by **content** (magic bytes, size, resolution and a blur check), so a renamed PDF or a blurry photo is rejected with a clear error before any paid AI call is made.
3. Gemini Flash reads the image and returns structured JSON: full name, document number, document type, legibility and a confidence score.
4. The service normalizes the data and looks for review reasons (low confidence, malformed number, same document or photo registered under another email). No reasons = `VERIFIED`; any reason = `NEEDS_REVIEW`. The record is stored with `CALL sp_create_onboarding(...)`.
5. The UI shows the extracted data, the OCR confidence, the status, the reasons for review and the registration timestamp.
6. An operator opens the **Admin panel** (protected with a key) to see statistics, search and filter every record, approve or reject the ones flagged `NEEDS_REVIEW`, export a CSV and erase the personal data of a record.

### Reliability features

* **Gemini contingency plan**: transient errors (429, 5xx, timeouts) are retried with exponential backoff, then a fallback model is tried, all inside a total time budget so the hosting request limit is never exceeded. If everything fails the user gets a controlled `502/503` and nothing is stored.
* **Cold-start notice**: free hosting sleeps after 15 minutes without traffic; the UI detects a slow server and says it is waking up instead of looking frozen.
* **Mobile friendly**: a "Take a photo" button opens the camera, and very large phone photos are shrunk in the browser before upload.
* **Request ids**: every response has an `X-Request-ID` header, and the same id appears in every log line of that request.

### Admin panel

Open it from the top bar and enter the operator key (`REVIEW_API_KEY`). The key lives only in the browser tab (`sessionStorage`).

* **Overview**: totals by status (click a card to open the filtered list), average OCR confidence, a status distribution bar and registrations of the last 7 days.
* **Records**: search by email or name, filter by status and date range, paginate, and export the filtered list as CSV (document numbers masked, spreadsheet formula injection neutralized).
* **Record detail**: full data, review reasons, a timeline (registered, flagged, decisions, erasure), approve / reject with a comment, and **erase personal data** (right to erasure).

### Security and privacy features

* **Operator endpoints are closed by default**: no `REVIEW_API_KEY` means `503 REVIEW_DISABLED`. The key is compared in constant time and repeated wrong keys from one IP are locked out (`429`).
* **Rate limiting** per IP on uploads (protects the free AI quota) and on the history lookup.
* **Security headers**: `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` and HSTS over HTTPS. Swagger (`/docs`) is exempt from the CSP because it loads its UI from a CDN.
* **Data minimization**: the image is never stored; there is no public lookup by record id; the public history masks document numbers.
* **Retention**: records older than `DATA_RETENTION_DAYS` (default 30) are anonymized automatically by a background job. Anonymizing replaces the name, document number, image hash and file name with placeholders, detaches the email and keeps only the audit trail. Operators can do the same manually.
* **Visible privacy notice** in the UI: this is a demo, do not upload real documents.

Diagrams: [sequence](docs/diagrams/sequence.png) · [architecture](docs/diagrams/architecture.png) · [data model](docs/diagrams/data-model.png)
(Mermaid sources are in `docs/diagrams/*.mmd`). UI mockup: [docs/mockup.html](docs/mockup.html) / [docs/mockup.png](docs/mockup.png).

## Why this stack

| Choice | Reason |
|---|---|
| **FastAPI (Python)** | Native `multipart/form-data` support, Pydantic validation, and Swagger/OpenAPI docs generated automatically (requirement R3.12). |
| **React + Vite** | Small, fast SPA; the UI is only a form and a result panel. |
| **MySQL + stored procedures** | Required by the challenge. All writes and reads go through `sp_*` procedures, which keeps SQL out of the application code and makes the insert transactional. |
| **Gemini Flash** | One multimodal call extracts structured data straight from the image (no OCR + parsing pipeline), has a free tier for development, and supports JSON-schema output. |
| **Render + Aiven + one Docker image** | The API also serves the built frontend, so the deployment is just *app + MySQL*, with no CORS to configure. Both services have a free tier. |

## Project structure

```
backend/app/
  routers/        HTTP only (no business logic): onboarding, reviews, admin, chat, health
  services/       business logic: image validation, OCR provider, onboarding flow, admin (stats, search, CSV, erasure), FAQ retrieval (RAG)
  repositories/   data access, calls stored procedures only
  core/           settings (env vars), error model, MySQL pool, SQL script runner, operator auth, rate limiter, retention job
  prompts.py      every prompt sent to the AI service (mirrored in PROMPTS.md)
backend/tests/    pytest suite (unit + API tests, no network or database needed)
frontend/src/     React app (onboarding flow, admin panel, API client, EN/ES strings, light/dark theme)
database/         schema.sql and stored_procedures.sql
docs/             diagrams, mockup, defense notes
samples/          fake test files (generated by scripts/generate_samples.py)
```

## Run locally

### Option A - Docker (easiest)

```bash
cp .env.example .env          # then set GEMINI_API_KEY
docker compose up --build
```

Open http://localhost:8000 (app) and http://localhost:8000/docs (Swagger).
The database schema and stored procedures are applied automatically on startup.

### Option B - Manual

Requirements: Python 3.11+, Node 20+, MySQL 8+.

```bash
# 1. Database
mysql -u root -p -e "CREATE DATABASE mini_kyc CHARACTER SET utf8mb4;"

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env                                # set DB_PASSWORD and GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000              # applies database/*.sql on startup

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173 (proxies /api to :8000)
```

To apply the SQL by hand instead: `mysql -u root -p mini_kyc < database/schema.sql` and `... < database/stored_procedures.sql`
(then set `AUTO_MIGRATE=false`).

### Try it without a Gemini key

Set `OCR_PROVIDER=mock`. The API then returns fixed fake data, which is useful to check the pipeline end to end
(upload, validation, stored procedure, UI). **Never deploy with `mock`.**

### Test files

`samples/sample_id_sharp.png` (fake ID, should be read), `samples/sample_id_blurry.png` (should return `422 BLURRY_IMAGE`)
and `samples/sample_unsupported.pdf` (should return `415 UNSUPPORTED_FILE_TYPE`).
Regenerate them with `python scripts/generate_samples.py`.

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | - | Google AI Studio key. **Never commit it.** |
| `GEMINI_MODEL` | `gemini-flash-latest` | Any Gemini Flash model your key can use (the live app uses `gemini-3.5-flash-lite`). |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.6-flash` | Tried when the primary model keeps failing. Empty disables the fallback. |
| `GEMINI_TIMEOUT_SECONDS` | `40` | Timeout of each Gemini call. |
| `GEMINI_MAX_ATTEMPTS` | `3` | Attempts per model for transient errors (backoff 1 s, 2 s, 4 s...). |
| `REVIEW_API_KEY` | empty | Secret for the operator and admin endpoints (`X-Review-Key` header). **Empty = they are disabled.** |
| `DATA_RETENTION_DAYS` | `30` | Records older than this are anonymized automatically. `0` keeps them forever. |
| `RETENTION_CHECK_HOURS` | `6` | How often the retention job runs while the server is awake (it also runs at startup). |
| `RATE_LIMIT_UPLOADS_PER_MINUTE` | `10` | Uploads per IP per minute. `0` disables the limit. |
| `RATE_LIMIT_HISTORY_PER_MINUTE` | `30` | History lookups per IP per minute. `0` disables the limit. |
| `RATE_LIMIT_ADMIN_FAILURES` / `RATE_LIMIT_ADMIN_WINDOW_SECONDS` | `5` / `300` | Wrong operator keys allowed per IP in the window before it is locked out. |
| `SECURITY_HEADERS_ENABLED` | `true` | Adds the security headers and the CSP. |
| `DUPLICATE_CHECK_ENABLED` | `true` | Flag the same document number / photo registered under another email. |
| `OCR_PROVIDER` | `gemini` | `gemini` or `mock` (demo/tests only). |
| `DB_HOST` `DB_PORT` `DB_USER` `DB_PASSWORD` `DB_NAME` | localhost / 3306 / root / - / mini_kyc | MySQL connection. Railway's `MYSQLHOST`, `MYSQLPORT`... names are also accepted. |
| `AUTO_MIGRATE` | `true` | Apply `database/*.sql` on startup (idempotent). |
| `BLUR_THRESHOLD` | `25` | Minimum sharpness (variance of the Laplacian). Raise it to reject more images. |
| `MIN_VERIFIED_CONFIDENCE` | `0.85` | Below this the record is `NEEDS_REVIEW`. |
| `CORS_ORIGINS` | empty | Only needed if the frontend is hosted on another origin. |

## API

Interactive documentation: **`/docs`** (Swagger UI) and `/openapi.json`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/onboarding` | `multipart/form-data`: `email` + `document` (JPG/PNG). Returns `201` with the stored record. |
| `GET` | `/api/v1/onboarding?email=...` | History of an email (document numbers masked, rate limited). |
| `POST` | `/api/v1/chat` | FAQ chatbot (RAG): `{"question": "..."}`. |
| `GET` | `/api/v1/reviews/pending` | Operator: records waiting for a decision. Needs the `X-Review-Key` header. |
| `POST` | `/api/v1/reviews/{id}` | Operator: `{"decision": "APPROVED" \| "REJECTED", "reviewer": "...", "comment": "..."}`. Needs `X-Review-Key`. |
| `GET` | `/api/v1/admin/overview` | Admin: statistics and registrations of the last days. Needs `X-Review-Key`. |
| `GET` | `/api/v1/admin/onboardings` | Admin: search with `status`, `q`, `date_from`, `date_to`, `limit`, `offset`. |
| `GET` | `/api/v1/admin/export.csv` | Admin: same filters, downloads a CSV (masked numbers). |
| `GET` | `/api/v1/admin/onboardings/{id}` | Admin: one record with its audit timeline. |
| `POST` | `/api/v1/admin/onboardings/{id}/anonymize` | Admin: erase the personal data of a record `{"reviewer": "...", "reason": "..."}`. |
| `GET` | `/api/v1/health` | Service and database status. |

Example:

```bash
curl -X POST http://localhost:8000/api/v1/onboarding \
  -F "email=maria@example.com" -F "document=@samples/sample_id_sharp.png"
```

### Error handling

Every error is JSON in the same shape, `{"error": {"code": "...", "message": "..."}}`. The API never returns a bare 500 for bad input.

| Status | Code | When |
|---|---|---|
| 400 | `EMPTY_FILE` | Empty upload |
| 413 | `FILE_TOO_LARGE` | Larger than 5 MB |
| 415 | `UNSUPPORTED_FILE_TYPE` | Not JPG/PNG (checked by content, not by file name) |
| 422 | `INVALID_EMAIL` / `VALIDATION_ERROR` | Bad email or missing fields |
| 422 | `BLURRY_IMAGE` / `IMAGE_TOO_SMALL` / `INVALID_IMAGE` | Image cannot be read reliably |
| 422 | `NOT_AN_IDENTITY_DOCUMENT` / `EXTRACTION_FAILED` | The AI could not find the name and number |
| 401 | `UNAUTHORIZED` | Missing or wrong `X-Review-Key` on the operator endpoints |
| 404 | `NOT_FOUND` | Unknown record id |
| 422 | `INVALID_FILTER` | Bad status or date range in the admin search |
| 429 | `TOO_MANY_REQUESTS` | Rate limit reached or operator key locked out (see the `Retry-After` header) |
| 409 | `NOT_PENDING_REVIEW` / `CONFLICT` | The record is not waiting for review (already decided, or already `VERIFIED`) |
| 502 / 503 | `OCR_PROVIDER_ERROR` / `OCR_RATE_LIMITED` / `OCR_NOT_CONFIGURED` / `REVIEW_DISABLED` / `DATABASE_UNAVAILABLE` | Upstream service problems, or operator review not enabled |

## Data and privacy

* Stored: email, extracted name and document number, document type, OCR confidence, status, the reasons for review, the operator's decision (name, comment, time), a SHA-256 hash of the image, the original file name and a UTC timestamp.
* The history shown in the UI and the CSV export mask the document number (only the last 3 characters are visible); only the admin detail shows it in full.
* **The image itself is not stored.** It is only sent to the AI service to read the text.
* **Erasure and retention:** records are anonymized after `DATA_RETENTION_DAYS` or on an operator's request (the audit trail stays, the personal data does not).
* The OCR confidence is the **model's own estimate**, not a calibrated probability. That is why low-confidence records are flagged for manual review instead of being rejected.
* Secrets are read from environment variables only; `.env` is git-ignored.
* If you use the Gemini free tier, Google may use submitted content to improve its products and human reviewers may read it. **Test with fake documents** (see `samples/`), not real IDs. A production system would use a paid tier or a provider with a data-processing agreement.

## Tests

```bash
cd backend
pytest
```

The suite covers image validation (type, size, resolution, blur), the onboarding flow (statuses, rejection paths, review flags, duplicates),
the operator review rules, the admin dashboard (statistics, filters, CSV, erasure, retention), the rate limiter, the Gemini retry / fallback / time-budget logic, OCR output parsing, the FAQ retrieval, the SQL script splitter
(including a regression test for the collation bug), the API contract (status codes, error bodies, request ids, security headers, rate limits, operator authentication) and
a check that `PROMPTS.md` contains every runtime prompt. None of them needs the network.

**Integration tests against a real MySQL 8** (`tests/test_mysql_integration.py`) run the migrations, the stored procedures and the whole service.
They are skipped unless `RUN_DB_TESTS=1`:

```bash
RUN_DB_TESTS=1 DB_HOST=127.0.0.1 DB_USER=root DB_PASSWORD=... DB_NAME=mini_kyc pytest tests/test_mysql_integration.py
```

### Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request: the full backend suite against a MySQL 8 service container,
the frontend production build, and the Docker image build.

## Deploy (free tier: Render + Aiven)

1. Push this repository to GitHub (public).
2. **Database:** create a free MySQL service on [Aiven](https://aiven.io) (Free plan). Copy its host, port, user, password and database name.
3. **App:** on [Render](https://render.com) create a **Web Service** from the GitHub repo. It detects the root `Dockerfile` and injects `PORT`; pick the **Free** instance.
4. Add these environment variables to the Render service:
   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `GEMINI_API_KEY`, `REVIEW_API_KEY` (enables the admin panel) and optionally `GEMINI_MODEL`, `DATA_RETENTION_DAYS` and the `RATE_LIMIT_*` values.
5. Open `https://<your-service>.onrender.com/api/v1/health`: it should report `{"status":"ok","database":"up"}`.
6. Optional: an UptimeRobot monitor on that URL keeps the instance awake, but Render's free plan gives 750 instance-hours per month shared by all your free services, and a 24/7 monitor uses almost all of them. Enable it only around demos and the defense.

The schema and stored procedures are applied automatically on startup. Note that the free Render instance sleeps after 15 minutes without traffic,
so the first request after a pause can take up to a minute.

## Known limitations / next steps

* No end-user authentication: the history is looked up by email alone (document numbers are masked, but anyone who knows an email can see its records). Real use needs a login or a one-time code sent to the email.
* The admin panel uses one shared key; use real authentication, roles and per-operator audit before any real use.
* Rate limiting is in memory and per instance, and the client IP comes from `X-Forwarded-For`, which a determined client can spoof. It stops accidents, scripts and quota exhaustion, not a targeted attack; production would use the platform's or a shared (Redis) limiter.
* The free hosting gives no encryption-at-rest guarantees beyond the provider's defaults; the demo should only hold fake data.
* The blur check uses a sharpness heuristic; very sparse documents can score low. Tune `BLUR_THRESHOLD`.
* Gemini model names change over time; if a model is retired, set `GEMINI_MODEL` to a current Flash model.
* Chatbot retrieval is TF-IDF over a small FAQ. For a larger knowledge base, replace it with embeddings and a vector store.
