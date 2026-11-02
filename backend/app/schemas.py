"""Pydantic models: API contracts and internal data carriers."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentType = Literal["DNI", "CE", "PASSPORT", "OTHER"]
# VERIFIED / NEEDS_REVIEW are set automatically; APPROVED / REJECTED are the operator's decision on a NEEDS_REVIEW record.
# ERASED: the personal data was anonymized (by an operator or by the retention policy).
OnboardingStatus = Literal["VERIFIED", "NEEDS_REVIEW", "APPROVED", "REJECTED", "ERASED"]
ReviewDecision = Literal["APPROVED", "REJECTED"]


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
    flags: tuple[str, ...] = ()  # why the record needs a human look (see FLAG_* constants)


@dataclass(frozen=True)
class DuplicateSignals:
    """How many records of OTHER emails share the document number / image with a new upload."""

    same_number_other_email: int = 0
    same_image_other_email: int = 0


FLAG_LOW_CONFIDENCE = "LOW_CONFIDENCE"
FLAG_INVALID_DOCUMENT_NUMBER = "INVALID_DOCUMENT_NUMBER"
FLAG_DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"
FLAG_DUPLICATE_IMAGE = "DUPLICATE_IMAGE"


# ---------- API ----------


class OnboardingResponse(BaseModel):
    id: int
    email: str
    document_type: DocumentType
    full_name: str
    document_number: str
    ocr_confidence: float = Field(description="OCR confidence as a percentage (0-100).")
    status: OnboardingStatus = Field(
        description="Automatic result (VERIFIED / NEEDS_REVIEW), or the operator's decision (APPROVED / REJECTED)."
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Reasons for manual review: LOW_CONFIDENCE, INVALID_DOCUMENT_NUMBER, DUPLICATE_DOCUMENT, DUPLICATE_IMAGE.",
    )
    original_filename: str | None = None
    created_at: datetime = Field(description="UTC timestamp of the registration.")
    reviewed_by: str | None = Field(None, description="Operator who approved or rejected the record.")
    review_comment: str | None = None
    reviewed_at: datetime | None = Field(None, description="UTC timestamp of the operator's decision.")


class ReviewRequest(BaseModel):
    decision: ReviewDecision
    reviewer: str = Field("operator", min_length=1, max_length=100, description="Name of the operator.")
    comment: str | None = Field(None, max_length=500)


class AnonymizeRequest(BaseModel):
    reviewer: str = Field("operator", min_length=1, max_length=100, description="Name of the operator.")
    reason: str | None = Field(None, max_length=200, description="Why the personal data is erased.")


# ---------- admin dashboard ----------


class AdminStats(BaseModel):
    total: int
    verified: int
    needs_review: int = Field(description="Flagged records that still wait for an operator.")
    approved: int
    rejected: int
    erased: int
    avg_confidence: float = Field(description="Average OCR confidence as a percentage (0-100).")


class DailyCount(BaseModel):
    day: date
    total: int


class AdminOverview(BaseModel):
    stats: AdminStats
    last_days: list[DailyCount] = Field(description="Registrations per UTC day, oldest first, zero-filled.")


class AdminPage(BaseModel):
    items: list[OnboardingResponse]
    total: int = Field(description="Number of records that match the filters (before pagination).")
    limit: int
    offset: int


class OnboardingEvent(BaseModel):
    event_type: str = Field(description="REGISTERED, FLAGGED, APPROVED, REJECTED or ANONYMIZED.")
    actor: str | None = None
    detail: str | None = None
    occurred_at: datetime


class OnboardingDetail(BaseModel):
    record: OnboardingResponse
    events: list[OnboardingEvent]


@dataclass(frozen=True)
class AdminFilters:
    """Filters of the admin record list (empty / None = no filter)."""

    status: str = ""
    query: str = ""
    date_from: date | None = None
    date_to: date | None = None


def mask_document_number(value: str) -> str:
    """Keep only the last 3 characters visible (privacy by default for lists and exports)."""
    if len(value) <= 3:
        return value
    return "*" * (len(value) - 3) + value[-3:]


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
