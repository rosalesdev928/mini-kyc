from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.dependencies import get_repository
from app.repositories.onboarding_repository import OnboardingRepository
from app.schemas import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["Health"])


# HEAD is accepted too (hidden from Swagger) because uptime monitors probe with HEAD by default.
@router.head("/health", include_in_schema=False)
@router.get("/health", response_model=HealthResponse, summary="Service and database health")
async def health(repository: OnboardingRepository = Depends(get_repository)) -> HealthResponse:
    database_up = await run_in_threadpool(repository.ping)
    return HealthResponse(
        status="ok" if database_up else "degraded", database="up" if database_up else "down"
    )
