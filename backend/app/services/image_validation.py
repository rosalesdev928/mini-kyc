"""Validation of uploaded identity images: type, size, resolution and blur."""

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from app.core.config import Settings
from app.core.errors import (
    BlurryImageError,
    EmptyFileError,
    FileTooLargeError,
    ImageTooSmallError,
    InvalidImageError,
    UnsupportedFileTypeError,
)

_LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
_ANALYSIS_MAX_SIDE = 1000


@dataclass(frozen=True)
class ValidatedImage:
    data: bytes
    mime_type: str
    width: int
    height: int
    sharpness: float
    sha256: str


def detect_mime_type(data: bytes) -> str | None:
    """Detect JPEG/PNG from magic bytes. The client-sent Content-Type is not trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def measure_sharpness(image: Image.Image) -> float:
    """Variance of the Laplacian: low values mean few sharp edges (a blurry image)."""
    gray = image.convert("L")
    longest = max(gray.size)
    if longest > _ANALYSIS_MAX_SIDE:
        factor = _ANALYSIS_MAX_SIDE / longest
        gray = gray.resize((round(gray.width * factor), round(gray.height * factor)))
    filtered = gray.filter(_LAPLACIAN)
    # Pillow copies the outermost pixel ring unfiltered; crop it so it cannot skew the variance.
    filtered = filtered.crop((1, 1, filtered.width - 1, filtered.height - 1))
    return float(ImageStat.Stat(filtered).var[0])


def validate_upload(data: bytes, settings: Settings) -> ValidatedImage:
    if not data:
        raise EmptyFileError("The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise FileTooLargeError(f"The file exceeds the {limit_mb:g} MB limit.")

    mime_type = detect_mime_type(data)
    if mime_type is None:
        raise UnsupportedFileTypeError("Only JPG and PNG images are supported.")

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            if min(width, height) < settings.min_image_side_px:
                raise ImageTooSmallError(
                    f"The image is too small ({width}x{height}px). "
                    f"The shortest side must be at least {settings.min_image_side_px}px."
                )
            sharpness = measure_sharpness(image)
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImageError("The file could not be read as an image.") from exc

    if sharpness < settings.blur_threshold:
        raise BlurryImageError(
            "The image is too blurry to read. Retake the photo in good light and keep the camera steady.",
            details={"sharpness": round(sharpness, 1), "minimum": settings.blur_threshold},
        )

    return ValidatedImage(
        data=data,
        mime_type=mime_type,
        width=width,
        height=height,
        sharpness=sharpness,
        sha256=hashlib.sha256(data).hexdigest(),
    )
