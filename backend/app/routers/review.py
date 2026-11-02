"""Operator endpoints: list the records waiting for review and approve / reject them.

These endpoints are protected with a shared secret sent in the `X-Review-Key` header
(`REVIEW_API_KEY` environment variable). If the variable is not set the endpoints are disabled.
A real system would use proper authentication (OIDC / JWT) and roles instead.
"""

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_review_key
from app.dependencies import get_onboarding_service
from app.schemas import ErrorResponse, OnboardingResponse, ReviewRequest
from app.services.onboarding_service import OnboardingService


router = APIRouter(
    prefix="/api/v1/reviews",
    tags=["Operator review"],
    dependencies=[Depends(require_review_key)],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid X-Review-Key."},
        429: {"model": ErrorResponse, "description": "Too many wrong keys from this IP."},
        503: {"model": ErrorResponse, "description": "Review disabled or database unavailable."},
    },
)


@router.get(
    "/pending",
    response_model=list[OnboardingResponse],
    summary="List the records waiting for a manual decision (oldest first)",
)
async def list_pending(
    service: OnboardingService = Depends(get_onboarding_service),
) -> list[OnboardingResponse]:
    return await run_in_threadpool(service.list_pending_reviews)


@router.post(
    "/{onboarding_id}",
    response_model=OnboardingResponse,
    summary="Approve or reject a record flagged NEEDS_REVIEW",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "The record is not pending review."},
    },
)
async def review_record(
    onboarding_id: int,
    body: ReviewRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    return await run_in_threadpool(
        service.review, onboarding_id, body.decision, body.reviewer, body.comment
    )
