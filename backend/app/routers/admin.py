"""Admin dashboard endpoints: statistics, filtered records, audit trail, CSV export and personal data erasure.

Protected with the same shared secret as the operator review (`X-Review-Key`, see app.core.auth).
No business logic here: the router only adapts HTTP to the services.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_review_key
from app.dependencies import get_admin_service
from app.schemas import (
    AdminOverview,
    AdminPage,
    AnonymizeRequest,
    ErrorResponse,
    OnboardingDetail,
    OnboardingResponse,
)
from app.services.admin_service import AdminService, build_filters

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin dashboard"],
    dependencies=[Depends(require_review_key)],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid X-Review-Key."},
        429: {"model": ErrorResponse, "description": "Too many wrong keys from this IP."},
        503: {"model": ErrorResponse, "description": "Admin disabled or database unavailable."},
    },
)

StatusFilter = Literal["VERIFIED", "NEEDS_REVIEW", "APPROVED", "REJECTED", "ERASED"]


@router.get(
    "/overview",
    response_model=AdminOverview,
    summary="Totals by status and registrations per day (last 7 days)",
)
async def overview(service: AdminService = Depends(get_admin_service)) -> AdminOverview:
    return await run_in_threadpool(service.overview)


@router.get(
    "/onboardings",
    response_model=AdminPage,
    summary="Search and filter onboarding records (newest first)",
    responses={422: {"model": ErrorResponse, "description": "Invalid filter."}},
)
async def list_onboardings(
    status: StatusFilter | None = Query(None, description="Effective status."),
    q: str | None = Query(None, max_length=100, description="Text in the email, name or document number."),
    date_from: date | None = Query(None, description="First UTC day, inclusive (YYYY-MM-DD)."),
    date_to: date | None = Query(None, description="Last UTC day, inclusive (YYYY-MM-DD)."),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AdminService = Depends(get_admin_service),
) -> AdminPage:
    filters = build_filters(status, q, date_from, date_to)
    return await run_in_threadpool(service.search, filters, limit, offset)


@router.get(
    "/export.csv",
    summary="Download the filtered records as CSV (document numbers masked)",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV file."}},
)
async def export_csv(
    status: StatusFilter | None = Query(None),
    q: str | None = Query(None, max_length=100),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    filters = build_filters(status, q, date_from, date_to)
    content = await run_in_threadpool(service.export_csv, filters)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="onboardings.csv"'},
    )


@router.get(
    "/onboardings/{onboarding_id}",
    response_model=OnboardingDetail,
    summary="One record with its audit trail",
    responses={404: {"model": ErrorResponse}},
)
async def get_detail(
    onboarding_id: int, service: AdminService = Depends(get_admin_service)
) -> OnboardingDetail:
    return await run_in_threadpool(service.detail, onboarding_id)


@router.post(
    "/onboardings/{onboarding_id}/anonymize",
    response_model=OnboardingResponse,
    summary="Erase the personal data of a record (name, document number, email, photo hash)",
    description=(
        "The row stays for statistics and audit, but its personal data is replaced and the erasure is logged. "
        "This cannot be undone."
    ),
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def anonymize(
    onboarding_id: int,
    body: AnonymizeRequest,
    service: AdminService = Depends(get_admin_service),
) -> OnboardingResponse:
    return await run_in_threadpool(service.anonymize, onboarding_id, body.reviewer, body.reason)
