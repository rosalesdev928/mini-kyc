from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.dependencies import get_chat_service
from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/v1/chat", tags=["FAQ chatbot"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a question about the onboarding process",
    description="RAG chatbot: retrieves the relevant FAQ entries and answers from them only.",
)
async def ask(request: ChatRequest, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    return await run_in_threadpool(service.answer, request.question, request.language)
