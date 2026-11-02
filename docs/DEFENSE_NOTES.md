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
3. **Live demo**: sharp sample (success), blurry sample (422), PDF (415), then Swagger at `/docs`.
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

## 4. "Hardest technical challenge" - pick one you actually understood

* **Blur detection that does not depend on the AI.** Pillow's convolution filter leaves the outermost pixel ring unfiltered, which added a constant error to the sharpness score and made blurry images look sharper than they were. Cropping that ring fixed it, and I calibrated the threshold on synthetic sharp and blurred images.
* **Safe handling of untrusted uploads.** Reading only `max_size + 1` bytes to detect oversized files, detecting type by content, and mapping every failure to a specific HTTP status.
* **Making AI output reliable.** JSON schema + temperature 0 + strict parsing + fallbacks to a controlled error.

## 5. Questions to expect

* *What happens if Gemini is down or rate-limited?* -> `503 OCR_RATE_LIMITED` / `502 OCR_PROVIDER_ERROR`; the user gets a retry message and nothing is stored.
* *How would you scale it?* -> Stateless API (horizontal scaling), connection pool, async job queue for OCR, object storage if images must be kept.
* *How would you improve accuracy?* -> Cross-check with a second provider, validate DNI check digit, compare against a registry (RENIEC), human-in-the-loop for low confidence.
* *Security?* -> Add authentication, rate limiting, HTTPS only, encryption at rest, audit log, retention policy for PII.
* *What would you test next?* -> Integration tests against a real MySQL (testcontainers) and contract tests for the OCR provider.
