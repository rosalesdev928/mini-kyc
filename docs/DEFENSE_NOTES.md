# Defense notes (committee presentation)

The presentation is partly or fully in English. Do not read code line by line: explain the flow and defend your decisions.
Read the code once before presenting, so that every answer below is something you can explain in your own words.

## 1. 60-second pitch (English)

> "A digital bank wants to speed up customer registration. My proof of concept lets a user enter an email and upload an ID photo.
> The API first validates the image, then calls Gemini Flash to extract the name and document number as structured JSON,
> and finally stores the result through a MySQL stored procedure. Low-confidence readings are flagged for manual review instead of being trusted blindly."

## 2. Walk-through order

1. **Architecture diagram** (`docs/diagrams/architecture.png`): browser -> FastAPI (routers -> services -> repository) -> MySQL; services -> Gemini.
2. **Sequence diagram** (`docs/diagrams/sequence.png`): upload -> validation -> OCR -> stored procedure -> response, plus the error branch.
3. **Live demo**: sharp sample (success), blurry sample (422), PDF (415), the Admin panel (statistics, filters, approve a flagged record, export CSV, erase data), dark mode, then Swagger at `/docs`.
4. **Code tour**, only these files:
   * `backend/app/services/onboarding_service.py` - the business flow.
   * `backend/app/services/image_validation.py` - validation by content, blur detection.
   * `backend/app/services/ocr_service.py` - provider interface + Gemini implementation + output parsing.
   * `backend/app/repositories/onboarding_repository.py` and `database/stored_procedures.sql` - persistence.
5. **Best practices**, **stack justification**, **hardest challenge** (below).

## 3. Decisions you should be able to justify

| Decision | Short answer |
|---|---|
| Layers (router / service / repository) | Business logic is outside the controllers, so it is testable without HTTP or a database (see the fakes in `tests/helpers.py`). |
| OCR behind an interface (`OcrProvider`) | I can swap Gemini for AWS Rekognition or Azure without touching the business flow; a mock provider keeps tests offline. |
| Stored procedures | Required, and the create operation is atomic: it upserts the customer and inserts the record in one transaction. |
| Validate by magic bytes, not by file extension or Content-Type | The client controls both of those; the bytes cannot be faked without breaking the image. |
| Blur check before calling the AI | Saves cost and latency, and gives the user a precise message. Implemented as the variance of a Laplacian filter. |
| `VERIFIED` vs `NEEDS_REVIEW` | The model's confidence is self-reported, so I never treat it as ground truth: low confidence or an invalid number format goes to a human. |
| Not storing the image | Data minimization: only a hash is kept. |
| Structured output (JSON schema, temperature 0) | Deterministic, parseable answers; malformed output becomes a controlled 422, never a crash. |
| One Docker image serves API + frontend | Fewer moving parts to deploy and no CORS. |
| API keys in environment variables | Nothing sensitive in git; `.env` is ignored and `.env.example` documents the variables. |
| Retry + fallback model for Gemini | The free tier returns `503 high demand` and timeouts. Transient errors are retried with exponential backoff, then a second model is tried, inside a total time budget (so the host's request limit is never hit). Permanent errors (400/401/403) are not retried. |
| Flags instead of a single status | A record can need review for several reasons (low confidence, malformed number, same document or photo under another email). Each reason is stored in `onboarding_flags` (1 record : N flags), so the operator sees *why*. |
| Operator decisions as history | `onboarding_reviews` is append-only (1 record : N reviews); the latest decision wins. The review procedure locks the row, checks it is still pending and inserts, so two operators cannot both decide. |
| Review endpoints behind a key, disabled by default | `REVIEW_API_KEY` empty means the endpoints answer `503 REVIEW_DISABLED`, so a forgotten variable never exposes them. Compared with `hmac.compare_digest`. In a real system: OIDC/JWT and roles. |
| Explicit collation in the stored procedures | Aiven's MySQL defaults to `utf8mb4_0900_ai_ci` while the tables use `utf8mb4_unicode_ci`; comparing a parameter with a column raised error 1267 in production. Parameters now declare the collation, with a regression test. |
| CI with a real MySQL | GitHub Actions runs the whole suite against a MySQL 8 container, including integration tests of the migrations and the procedures. |
| Admin read model as a SQL view | `v_onboarding_details` joins customer, record, flags and the latest decision once, and computes `effective_status`. The list, detail and search procedures all read from it, so the status logic lives in one place. |
| Search with `COUNT(*) OVER ()` | One query returns the page and the total count, so pagination needs no second round trip. LIKE wildcards in the user's text are escaped. |
| Erasure by anonymization, not DELETE | The audit trail (who decided what, when) must survive, but the personal data must not. The procedure replaces name, number, image hash and file name, detaches the email and records who erased it and why. Retention runs the same procedure automatically after 30 days. |
| CSV export hardening | Cells starting with `=`, `+`, `-` or `@` are prefixed so a spreadsheet never runs them as formulas (CSV injection); numbers are masked; a BOM keeps accents correct in Excel. |
| Rate limiting and lockout | A sliding window per IP on uploads (also protects the free AI quota), on the history lookup and on wrong operator keys. It is in memory, so it is per instance and the IP header can be spoofed: a guard, not a security boundary. |
| Security headers and CSP | Strict CSP (no inline scripts: the theme script is an external file). `/docs` is exempt because Swagger UI loads assets from a CDN. |
| Removing the public lookup by id | Sequential ids made every record guessable. The only public read is the history by email, with masked numbers. |
| Request id in every log line | Makes it possible to follow one request across the middleware, the service and the repository (`X-Request-ID`). |

## 4. "Hardest technical challenge" - pick one you actually understood

* **Blur detection that does not depend on the AI.** Pillow's convolution filter leaves the outermost pixel ring unfiltered, which added a constant error to the sharpness score and made blurry images look sharper than they were. Cropping that ring fixed it, and I calibrated the threshold on synthetic sharp and blurred images.
* **Safe handling of untrusted uploads.** Reading only `max_size + 1` bytes to detect oversized files, detecting type by content, and mapping every failure to a specific HTTP status.
* **Making AI output reliable.** JSON schema + temperature 0 + strict parsing + fallbacks to a controlled error.
* **Production-only failures.** Two bugs only appeared after deploying: Gemini timing out at 30 s (fixed with a longer timeout, then with retries and a fallback model) and MySQL error 1267 "Illegal mix of collations" (the managed database had a different default collation; fixed in the procedures and covered by a regression test). Reading the logs, reproducing and adding a test for each one is a good story.

## 5. Questions to expect

* *What happens if Gemini is down or rate-limited?* -> It is retried with backoff, then a fallback model is tried; if everything fails the user gets `503 OCR_RATE_LIMITED` / `502 OCR_PROVIDER_ERROR` and nothing is stored.
* *What if the free server is asleep?* -> The UI pings `/health`, shows "waking up the server" if it is slow, and an uptime monitor can keep it awake during the demo (not 24/7: Render's free plan has a monthly hour budget).
* *Why is a record `NEEDS_REVIEW`?* -> The `flags` field says why (low confidence, bad number format, duplicate document or photo under another email). An operator approves or rejects it from the Admin panel.
* *Demo tip:* uploading the same photo with a *different* email is flagged as `DUPLICATE_IMAGE` on purpose (possible identity reuse). Use the same email to show `VERIFIED`, or a second email to show the review flow.
* *How would you scale it?* -> Stateless API (horizontal scaling), connection pool, async job queue for OCR, object storage if images must be kept.
* *How would you improve accuracy?* -> Cross-check with a second provider, validate DNI check digit, compare against a registry (RENIEC), human-in-the-loop for low confidence.
* *Security?* -> Already in: operator key (disabled by default, constant-time compare, lockout), rate limits, security headers + CSP, masked numbers, no image storage, retention + erasure. Still missing for real use: user authentication (the history is by email only), roles/OIDC for operators, a shared rate limiter, encryption at rest and a data-processing agreement with the AI provider (the Gemini free tier may use submitted content to improve Google's products).
* *Is the data safe on free hosting?* -> It is a demo with fake documents: TLS in transit, secrets in env vars, minimal data, automatic anonymization. A real bank would use paid managed services, private networking, backups and a compliant AI contract.
* *Why is the admin tied to one key?* -> Scope of a PoC. Production: SSO/OIDC, roles (reviewer vs. admin), per-user audit.
* *What would you test next?* -> Integration tests against a real MySQL (testcontainers) and contract tests for the OCR provider.
