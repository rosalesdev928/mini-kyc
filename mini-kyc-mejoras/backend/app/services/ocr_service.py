"""OCR providers. The rest of the app depends only on the OcrProvider interface."""

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.core.errors import (
    AppError,
    ExtractionFailedError,
    OcrProviderError,
    OcrRateLimitedError,
)
from app.prompts import OCR_SYSTEM_INSTRUCTION, OCR_USER_PROMPT
from app.schemas import ExtractedDocument
from app.services.gemini_client import create_gemini_client

logger = logging.getLogger(__name__)


class OcrProvider(Protocol):
    def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedDocument: ...


class _GeminiResponseSchema(BaseModel):
    """Plain schema sent to Gemini (no constraints or defaults, which the SDK may not convert)."""

    is_identity_document: bool
    is_legible: bool
    document_type: Literal["DNI", "CE", "PASSPORT", "OTHER"]
    full_name: str | None
    document_number: str | None
    confidence: float


class _ModelOutput(BaseModel):
    """Strict validation of what the model returned."""

    is_identity_document: bool
    is_legible: bool
    document_type: Literal["DNI", "CE", "PASSPORT", "OTHER"] = "OTHER"
    full_name: str | None = None
    document_number: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


def parse_model_output(raw_text: str) -> ExtractedDocument:
    """Turn the model's JSON text into an ExtractedDocument, tolerating code fences."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        output = _ModelOutput.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Unparseable OCR output: %s", exc)
        raise ExtractionFailedError(
            "The AI service returned an unexpected answer. Please try again with a clearer photo."
        ) from exc

    return ExtractedDocument(
        is_identity_document=output.is_identity_document,
        is_legible=output.is_legible,
        document_type=output.document_type,
        full_name=(output.full_name or "").strip() or None,
        document_number=(output.document_number or "").strip() or None,
        confidence=output.confidence,
    )


# Transient failures worth retrying: rate limit, server errors and gateway timeouts.
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_MODEL_NOT_FOUND = 404


class GeminiOcrProvider:
    """Gemini implementation with retries (exponential backoff) and a fallback model.

    Contingency plan for the free tier, where "503 high demand" and timeouts happen:
    1. retry the primary model on transient errors,
    2. then try the fallback model,
    3. stop when the total time budget is spent, so the hosting request limit is never hit.
    """

    def __init__(
        self,
        settings: Settings,
        client=None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._settings = settings
        self._client = client
        self._sleep = sleep
        self._clock = clock

    def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedDocument:
        from google.genai import types

        client = self._client or create_gemini_client(self._settings)
        self._client = client

        deadline = self._clock() + self._settings.gemini_total_budget_seconds
        last_status: int | None = None
        failures = 0

        for model in self._models():
            for attempt in range(1, max(1, self._settings.gemini_max_attempts) + 1):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            OCR_USER_PROMPT,
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=OCR_SYSTEM_INSTRUCTION,
                            response_mime_type="application/json",
                            response_schema=_GeminiResponseSchema,
                            temperature=0.0,
                        ),
                    )
                    document = parse_model_output(response.text or "")
                except AppError:
                    raise  # e.g. an unreadable answer: a controlled error, retrying will not help
                except Exception as exc:  # SDK errors vary by version; map them by status code
                    failures += 1
                    last_status = getattr(exc, "code", None)
                    logger.warning(
                        "Gemini attempt %d/%d with model %s failed (status=%s): %s",
                        attempt, self._settings.gemini_max_attempts, model, last_status, exc,
                    )
                    if last_status == _MODEL_NOT_FOUND:
                        break  # this model name is not available to the key: go to the next model
                    if last_status is not None and last_status not in _RETRYABLE_STATUSES:
                        raise OcrProviderError("The AI service could not process the document.") from exc
                    delay = self._settings.gemini_retry_base_seconds * (2 ** (attempt - 1))
                    if attempt == self._settings.gemini_max_attempts:
                        break  # attempts for this model are spent: go to the next model
                    if self._clock() + delay >= deadline:
                        return self._give_up(last_status, failures)
                    self._sleep(delay)
                    continue

                if failures:
                    logger.info("OCR succeeded with model %s after %d failed attempt(s).", model, failures)
                return document

            if self._clock() >= deadline:
                break

        return self._give_up(last_status, failures)

    def _models(self) -> list[str]:
        models = [self._settings.gemini_model]
        fallback = self._settings.gemini_fallback_model.strip()
        if fallback and fallback not in models:
            models.append(fallback)
        return models

    @staticmethod
    def _give_up(last_status: int | None, failures: int):
        logger.error("Gemini failed after %d attempt(s) (last status=%s).", failures, last_status)
        if last_status == 429:
            raise OcrRateLimitedError("The AI service is busy right now. Please try again in a minute.")
        raise OcrProviderError(
            "The AI service is not responding right now. Please try again in a minute."
        )


class MockOcrProvider:
    """Deterministic fake used ONLY for demos and tests (OCR_PROVIDER=mock)."""

    def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedDocument:
        return ExtractedDocument(
            is_identity_document=True,
            is_legible=True,
            document_type="DNI",
            full_name="Maria Fernandez Torres",
            document_number="12345678",
            confidence=0.98,
        )


def build_ocr_provider(settings: Settings) -> OcrProvider:
    if settings.ocr_provider == "mock":
        return MockOcrProvider()
    return GeminiOcrProvider(settings)
