import pytest

from app.core.config import Settings
from app.core.errors import (
    BlurryImageError,
    EmptyFileError,
    FileTooLargeError,
    ImageTooSmallError,
    UnsupportedFileTypeError,
)
from app.services.image_validation import detect_mime_type, validate_upload
from tests.helpers import make_blurry_image, make_document_image

SETTINGS = Settings(max_upload_bytes=200_000)


def test_valid_png_is_accepted():
    image = validate_upload(make_document_image(), SETTINGS)
    assert image.mime_type == "image/png"
    assert image.sharpness > SETTINGS.blur_threshold
    assert len(image.sha256) == 64


def test_valid_jpeg_is_accepted():
    image = validate_upload(make_document_image(fmt="JPEG"), SETTINGS)
    assert image.mime_type == "image/jpeg"


def test_empty_file_is_rejected():
    with pytest.raises(EmptyFileError):
        validate_upload(b"", SETTINGS)


def test_oversized_file_is_rejected():
    with pytest.raises(FileTooLargeError):
        validate_upload(b"\xff\xd8\xff" + b"0" * 300_000, SETTINGS)


@pytest.mark.parametrize("payload", [b"%PDF-1.7 fake pdf", b"GIF89a....", b"plain text file"])
def test_unsupported_types_are_rejected_by_content_not_by_name(payload):
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(payload, SETTINGS)


def test_tiny_image_is_rejected():
    with pytest.raises(ImageTooSmallError):
        validate_upload(make_document_image(width=120, height=80), SETTINGS)


def test_blurry_image_is_rejected():
    with pytest.raises(BlurryImageError) as error:
        validate_upload(make_blurry_image(), SETTINGS)
    assert error.value.status_code == 422


def test_detect_mime_type_uses_magic_bytes():
    assert detect_mime_type(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert detect_mime_type(b"\xff\xd8\xff\xe0....") == "image/jpeg"
    assert detect_mime_type(b"hello") is None
