"""Domain errors that map to controlled HTTP responses (never a generic 500)."""


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, details: object | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidEmailError(AppError):
    status_code = 422
    code = "INVALID_EMAIL"


class EmptyFileError(AppError):
    status_code = 400
    code = "EMPTY_FILE"


class FileTooLargeError(AppError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "UNSUPPORTED_FILE_TYPE"


class InvalidImageError(AppError):
    status_code = 422
    code = "INVALID_IMAGE"


class ImageTooSmallError(AppError):
    status_code = 422
    code = "IMAGE_TOO_SMALL"


class BlurryImageError(AppError):
    status_code = 422
    code = "BLURRY_IMAGE"


class NotAnIdentityDocumentError(AppError):
    status_code = 422
    code = "NOT_AN_IDENTITY_DOCUMENT"


class ExtractionFailedError(AppError):
    status_code = 422
    code = "EXTRACTION_FAILED"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class OcrNotConfiguredError(AppError):
    status_code = 503
    code = "OCR_NOT_CONFIGURED"


class OcrRateLimitedError(AppError):
    status_code = 503
    code = "OCR_RATE_LIMITED"


class OcrProviderError(AppError):
    status_code = 502
    code = "OCR_PROVIDER_ERROR"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "DATABASE_UNAVAILABLE"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ReviewDisabledError(AppError):
    status_code = 503
    code = "REVIEW_DISABLED"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class NotPendingReviewError(ConflictError):
    code = "NOT_PENDING_REVIEW"


class InvalidFilterError(AppError):
    status_code = 422
    code = "INVALID_FILTER"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "TOO_MANY_REQUESTS"

    def __init__(self, message: str, *, retry_after_seconds: int = 60):
        super().__init__(message)
        self.headers = {"Retry-After": str(retry_after_seconds)}
