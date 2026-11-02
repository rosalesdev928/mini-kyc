"""Dependency providers (composition root). Tests override these with fakes."""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.database import create_pool
from app.repositories.onboarding_repository import OnboardingRepository
from app.services.admin_service import AdminService
from app.services.chat_service import ChatService
from app.services.faq_service import FaqRetriever, load_faq
from app.services.ocr_service import build_ocr_provider
from app.services.onboarding_service import OnboardingService

FAQ_PATH = Path(__file__).parent / "data" / "faq.md"


@lru_cache
def get_repository() -> OnboardingRepository:
    return OnboardingRepository(create_pool(get_settings()))


@lru_cache
def _get_ocr_provider():
    return build_ocr_provider(get_settings())


@lru_cache
def _get_faq_retriever() -> FaqRetriever:
    return FaqRetriever(load_faq(FAQ_PATH))


def get_onboarding_service(
    settings: Settings = Depends(get_settings),
    repository: OnboardingRepository = Depends(get_repository),
) -> OnboardingService:
    return OnboardingService(repository, _get_ocr_provider(), settings)


def get_admin_service(
    settings: Settings = Depends(get_settings),
    repository: OnboardingRepository = Depends(get_repository),
) -> AdminService:
    return AdminService(repository, settings)


@lru_cache
def _get_chat_service() -> ChatService:
    return ChatService(_get_faq_retriever(), get_settings())


def get_chat_service() -> ChatService:
    return _get_chat_service()
