"""HTTP layer for onboarding. No business logic here: it only adapts HTTP to the service."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.rate_limit import limit_history, limit_uploads
from app.dependencies import get_onboarding_service
from app.schemas import ErrorResponse, OnboardingResponse
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])

_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Empty file."},
    413: {"model": ErrorResponse, "description": "File larger than the allowed size."},
    415: {"model": ErrorResponse, "description": "Unsupported file type (only JPG and PNG)."},
    422: {
        "model": ErrorResponse,
        "description": "Invalid email, blurry/small/unreadable image, or not an identity document.",
    },
    429: {"model": ErrorResponse, "description": "Too many uploads from this IP. See the Retry-After header."},
    502: {"model": ErrorResponse, "description": "The AI/OCR provider failed."},
    503: {"model": ErrorResponse, "description": "AI service or database unavailable."},
}


@router.post(
    "",
    response_model=OnboardingResponse,
    status_code=201,
    summary="Register an onboarding from an identity document image",
    description=(
        "Sequence: upload image -> validate -> AI/OCR extraction -> store through a stored procedure. "
        "Send `multipart/form-data` with an `email` field and a `document` file (JPG or PNG, max 5 MB)."
    ),
    responses=_ERROR_RESPONSES,
    dependencies=[Depends(limit_uploads)],
)
async def create_onboarding(
    email: str = Form(..., description="Customer email address."),
    document: UploadFile = File(..., description="Photo of the identity document (JPG or PNG)."),
    service: OnboardingService = Depends(get_onboarding_service),
    settings: Settings = Depends(get_settings),
) -> OnboardingResponse:
    # Read one byte more than the limit so oversized files are detected without loading them fully.
    content = await document.read(settings.max_upload_bytes + 1)
    return await run_in_threadpool(service.process, email, document.filename, content)


@router.get(
    "",
    response_model=list[OnboardingResponse],
    summary="List the recent onboarding records of an email (document numbers are masked)",
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse, "description": "Too many lookups from this IP."},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(limit_history)],
)
async def list_onboardings(
    email: str = Query(..., description="Customer email address."),
    service: OnboardingService = Depends(get_onboarding_service),
) -> list[OnboardingResponse]:
    return await run_in_threadpool(service.list_for_email, email)
