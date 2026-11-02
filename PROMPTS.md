# PROMPTS.md

All AI prompts used in this project, as required by deliverable 6 / requirement R3.4.

- **Part 1 - Runtime prompts:** the exact texts the application sends to the AI service (Gemini).
  They live in `backend/app/prompts.py`; a unit test (`test_prompts_md_lists_every_runtime_prompt`)
  fails if this file and the code ever differ.
- **Part 2 - Prompts given to the coding assistant:** the requests I wrote to Claude (Anthropic)
  while building the project, grouped by phase.

---

# Part 1 - Runtime prompts (Gemini Flash)

### 1.1 OCR - system instruction

Sent as the `system_instruction` of every document-extraction request.

```text
You are an OCR and data-extraction engine for a bank's KYC onboarding process.
You receive one photo or scan of an identity document (for example a Peruvian DNI, a foreigner card or a passport).
Extract only what is printed on the document. Never invent, guess or complete missing characters.
```

### 1.2 OCR - user prompt

Sent together with the uploaded image. The call uses `temperature=0`, `response_mime_type="application/json"`
and a JSON schema, so the answer is machine-readable. A malformed answer is rejected with a controlled `422 EXTRACTION_FAILED`.

```text
Analyze the attached image and return a JSON object with exactly these fields:

- is_identity_document (boolean): true only if the image shows an official identity document.
- is_legible (boolean): false if the text is too blurry, cropped, dark or glared to be read reliably.
- document_type (string): one of "DNI", "CE", "PASSPORT", "OTHER".
- full_name (string or null): the holder's full name in the order given names first, then surnames, in title case. Null if not readable.
- document_number (string or null): the main document number exactly as printed, without spaces. Null if not readable.
- confidence (number between 0 and 1): your confidence that full_name and document_number were read correctly.

Return only the JSON object, with no extra text.
```

### 1.3 FAQ chatbot (RAG) - prompt template

Bonus feature. `{context}` is replaced with the 1-3 FAQ entries retrieved for the question
(TF-IDF similarity over `backend/app/data/faq.md`), and `{question}` with the user's question.

```text
You are the support assistant of a digital bank's onboarding (KYC) process.
Answer the user's question using ONLY the FAQ context below.
If the context does not contain the answer, say you do not have that information and suggest contacting support.
Answer in the same language as the question, in at most four sentences.

FAQ context:
{context}

Question: {question}
```

---

# Part 2 - Prompts given to the coding assistant (Claude)

I used Claude (Anthropic) as a coding assistant during the whole project. I wrote my requests in Spanish;
this section groups them by phase and summarizes them in English (they are summaries, not word-for-word quotes).
Generated code was verified with the unit and integration tests, the CI pipeline and manual checks on the deployed app.

## Phase 1 - Understanding the challenge

- Read the challenge PDF (Onboarding Digital - Mini KYC, level 3) and explain the requirements, deliverables and acceptance checklist in simple words.
- Propose a stack and a plan. My constraints: React + FastAPI + MySQL with stored procedures, Gemini for OCR, and **no paid services**.

## Phase 2 - Architecture and database

- Design a layered backend (routers -> services -> repositories) and a data model for onboarding requests, documents and review events.
- Write the MySQL schema, a view and the stored procedures, so the backend never builds SQL by hand.
- Draw the architecture and data-model diagrams for the README.

## Phase 3 - Backend and OCR

- Build the upload endpoint with file validation (type and size).
- Integrate Gemini to extract the document type, full name and document number from the ID image, with retries, a fallback and a controlled error when the answer is malformed.
- Add a review flow: automatic flags (low confidence, illegible image, duplicates) and manual approve/reject.
- Write unit tests and MySQL integration tests.

## Phase 4 - Frontend

- Build the React + Vite onboarding form: upload the image, show the extracted fields, let the user correct them, then submit.
- Add English/Spanish translations and clear error messages.

## Phase 5 - Deployment and CI

- Prepare a Dockerfile and docker-compose for local use.
- Explain click by click how to deploy for free (Render for the app, Aiven free MySQL for the database) and how to set the environment variables without exposing keys.
- Add a GitHub Actions pipeline (backend tests with MySQL, frontend build, Docker build).

## Phase 6 - Documentation and deliverables

- Write the README in English (setup, environment variables, API table, known limitations).
- Create the UI mockup, defense notes (questions I may be asked and answers) and this PROMPTS.md.
- Check the repository against the acceptance checklist: public repo, no hardcoded keys, English code and commits, deployed URL.

## Phase 7 - Improvements I chose

- Admin panel: overview, records list with filters, record detail, approve/reject, CSV export, and erase personal data.
- Visual identity: logo, dark mode and a step indicator.
- Visible security: privacy notice, rate limiting, security headers, data retention and anonymization.
- Bonus chatbot: FAQ assistant that answers from a knowledge base (RAG).

## Phase 8 - Quality fixes, repository hygiene and delivery

- Chatbot: answer Spanish questions correctly (bilingual FAQ and a `language` parameter on the chat endpoint) and reset the conversation when the interface language changes.
- Admin panel: clarify that the operator sees all submitted records, protected by the review key.
- Diagnose failing CI runs from logs and screenshots, and fix the root cause (a rate-limit lockout interfering with an admin test).
- Verify the deployment on Render after each release (health check, Swagger docs, upload flow).
- Repository hygiene: normalize the commit history, remove stale branches and confirm that `main` is the only branch and contains no secrets.
- Final review against the acceptance checklist and guidance on completing the submission form.
- Review of this PROMPTS.md against deliverable 6, which led to adding Part 2.
