"""Business logic of the onboarding flow: validate -> OCR -> store."""

import re

from app.core.config import Settings
from app.core.errors import (
    BlurryImageError,
    ExtractionFailedError,
    InvalidEmailError,
    NotAnIdentityDocumentError,
    NotFoundError,
)
from app.repositories.onboarding_repository import OnboardingRepository
from app.schemas import ExtractedDocument, NewOnboarding, OnboardingResponse
from app.services.image_validation import validate_upload
from app.services.ocr_service import OcrProvider

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_DNI_WITH_CHECK_DIGIT = re.compile(r"^(\d{8})-\d$")
_DNI_PATTERN = re.compile(r"^\d{8}$")
_GENERIC_DOCUMENT_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")


def normalize_email(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if len(cleaned) > 254 or not _EMAIL_PATTERN.match(cleaned):
        raise InvalidEmailError("Enter a valid email address.")
    return cleaned


def normalize_document_number(raw_number: str, document_type: str) -> str:
    cleaned = re.sub(r"[\s.]", "", raw_number).upper()
    if document_type == "DNI":
        match = _DNI_WITH_CHECK_DIGIT.match(cleaned)
        if match:
            return match.group(1)  # drop the printed check digit
    return cleaned


def is_valid_document_number(number: str, document_type: str) -> bool:
    if document_type == "DNI":
        return bool(_DNI_PATTERN.match(number))
    return bool(_GENERIC_DOCUMENT_PATTERN.match(number))


class OnboardingService:
    def __init__(self, repository: OnboardingRepository, ocr: OcrProvider, settings: Settings):
        self._repository = repository
        self._ocr = ocr
        self._settings = settings

    def process(
        self, email: str, filename: str | None, image_bytes: bytes
    ) -> OnboardingResponse:
        normalized_email = normalize_email(email)
        image = validate_upload(image_bytes, self._settings)

        extracted = self._ocr.extract(image.data, image.mime_type)
        self._ensure_usable(extracted)

        number = normalize_document_number(extracted.document_number or "", extracted.document_type)
        status = (
            "VERIFIED"
            if extracted.confidence >= self._settings.min_verified_confidence
            and is_valid_document_number(number, extracted.document_type)
            else "NEEDS_REVIEW"
        )

        return self._repository.create(
            NewOnboarding(
                email=normalized_email,
                document_type=extracted.document_type,
                full_name=(extracted.full_name or "")[:200],
                document_number=number[:30],
                ocr_confidence=round(extracted.confidence * 100, 2),
                status=status,
                image_sha256=image.sha256,
                original_filename=filename[:255] if filename else None,
            )
        )

    def get(self, onboarding_id: int) -> OnboardingResponse:
        record = self._repository.get_by_id(onboarding_id)
        if record is None:
            raise NotFoundError(f"Onboarding record {onboarding_id} was not found.")
        return record

    def list_for_email(self, email: str) -> list[OnboardingResponse]:
        return self._repository.list_by_email(normalize_email(email))

    @staticmethod
    def _ensure_usable(extracted: ExtractedDocument) -> None:
        if not extracted.is_identity_document:
            raise NotAnIdentityDocumentError(
                "The image does not look like an identity document. Upload a photo of your ID."
            )
        if not extracted.is_legible:
            raise BlurryImageError(
                "The document text is not legible. Retake the photo in good light without glare."
            )
        if not extracted.full_name or not extracted.document_number:
            raise ExtractionFailedError(
                "The name and document number could not be read. Retake the photo showing the whole document."
            )
