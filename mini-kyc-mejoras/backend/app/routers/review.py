"""Operator endpoints: list the records waiting for review and approve / reject them.

These endpoints are protected with a shared secret sent in the `X-Review-Key` header
(`REVIEW_API_KEY` environment variable). If the variable is not set the endpoints are disabled.
A real system would use proper authentication (OIDC / JWT) and roles instead.
"""

import hmac

from fastapi import APIRouter, Depends, Header
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.errors import ReviewDisabledError, UnauthorizedError
from app.dependencies import get_onboarding_service
from app.schemas import ErrorResponse, OnboardingResponse, ReviewRequest
from app.services.onboarding_service import OnboardingService


def require_review_key(
    x_review_key: str | None = Header(None, description="Operator secret (REVIEW_API_KEY)."),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.review_api_key:
        raise ReviewDisabledError("Operator review is not enabled on this server.")
    supplied = (x_review_key or "").encode("utf-8")
    if not hmac.compare_digest(supplied, settings.review_api_key.encode("utf-8")):
        raise UnauthorizedError("Missing or invalid operator key.")


router = APIRouter(
    prefix="/api/v1/reviews",
    tags=["Operator review"],
    dependencies=[Depends(require_review_key)],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid X-Review-Key."},
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
