"""OCR providers. The rest of the app depends only on the OcrProvider interface."""

import json
import logging
import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.core.errors import (
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


class _ModelOutput(BaseModel):
    """Shape the model must return (also used as the JSON response schema)."""

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


class GeminiOcrProvider:
    def __init__(self, settings: Settings, client=None):
        self._settings = settings
        self._client = client

    def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedDocument:
        from google.genai import types

        client = self._client or create_gemini_client(self._settings)
        self._client = client
        try:
            response = client.models.generate_content(
                model=self._settings.gemini_model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    OCR_USER_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    system_instruction=OCR_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=_ModelOutput,
                    temperature=0.0,
                ),
            )
        except Exception as exc:  # SDK errors vary by version; map them by status code
            status = getattr(exc, "code", None)
            logger.error("Gemini request failed (status=%s): %s", status, exc)
            if status == 429:
                raise OcrRateLimitedError(
                    "The AI service is busy right now. Please try again in a minute."
                ) from exc
            raise OcrProviderError("The AI service could not process the document.") from exc

        return parse_model_output(response.text or "")


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
