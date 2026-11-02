"""Pydantic models: API contracts and internal data carriers."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentType = Literal["DNI", "CE", "PASSPORT", "OTHER"]
OnboardingStatus = Literal["VERIFIED", "NEEDS_REVIEW"]


# ---------- internal ----------


@dataclass(frozen=True)
class ExtractedDocument:
    """Normalized output of any OCR provider."""

    is_identity_document: bool
    is_legible: bool
    document_type: str
    full_name: str | None
    document_number: str | None
    confidence: float  # 0.0 - 1.0


@dataclass(frozen=True)
class NewOnboarding:
    email: str
    document_type: str
    full_name: str
    document_number: str
    ocr_confidence: float  # percentage 0 - 100
    status: str
    image_sha256: str
    original_filename: str | None


# ---------- API ----------


class OnboardingResponse(BaseModel):
    id: int
    email: str
    document_type: DocumentType
    full_name: str
    document_number: str
    ocr_confidence: float = Field(description="OCR confidence as a percentage (0-100).")
    status: OnboardingStatus
    original_filename: str | None = None
    created_at: datetime = Field(description="UTC timestamp of the registration.")


class ErrorBody(BaseModel):
    code: str = Field(examples=["BLURRY_IMAGE"])
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(description="FAQ entries used to build the answer.")
