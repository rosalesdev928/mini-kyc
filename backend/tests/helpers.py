"""Test helpers: synthetic images and in-memory fakes (no network, no database)."""

import io

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.schemas import ExtractedDocument, NewOnboarding, OnboardingResponse


def make_document_image(width: int = 900, height: int = 570, fmt: str = "PNG") -> bytes:
    """A sharp, synthetic ID-like card (clearly fake: it says SAMPLE)."""
    image = Image.new("RGB", (width, height), (236, 240, 244))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=26)
    draw.rectangle([20, 20, width - 20, height - 20], outline=(30, 60, 90), width=4)
    lines = ["SAMPLE ID CARD", "NOT A REAL DOCUMENT", "DNI 12345678", "FERNANDEZ TORRES", "MARIA"]
    for index, text in enumerate(lines):
        draw.text((50, 50 + index * 65), text, font=font, fill=(20, 40, 70))
    draw.rectangle([620, 120, 840, 380], fill=(150, 160, 175))
    return _encode(image, fmt)


def make_blurry_image() -> bytes:
    sharp = Image.open(io.BytesIO(make_document_image()))
    return _encode(sharp.filter(ImageFilter.GaussianBlur(5)), "PNG")


def _encode(image: Image.Image, fmt: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


class FakeOcr:
    def __init__(self, result: ExtractedDocument | None = None):
        self.calls = 0
        self.result = result or ExtractedDocument(
            is_identity_document=True,
            is_legible=True,
            document_type="DNI",
            full_name="Maria Fernandez Torres",
            document_number="12345678",
            confidence=0.97,
        )

    def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedDocument:
        self.calls += 1
        return self.result


class FakeRepository:
    """In-memory stand-in for OnboardingRepository."""

    def __init__(self):
        self.created: list[NewOnboarding] = []

    def create(self, new_record: NewOnboarding) -> OnboardingResponse:
        from datetime import datetime, timezone

        self.created.append(new_record)
        return OnboardingResponse(
            id=len(self.created),
            email=new_record.email,
            document_type=new_record.document_type,
            full_name=new_record.full_name,
            document_number=new_record.document_number,
            ocr_confidence=new_record.ocr_confidence,
            status=new_record.status,
            original_filename=new_record.original_filename,
            created_at=datetime.now(timezone.utc),
        )

    def get_by_id(self, onboarding_id: int):
        return None

    def list_by_email(self, email: str, limit: int = 20):
        return []

    def ping(self) -> bool:
        return True
