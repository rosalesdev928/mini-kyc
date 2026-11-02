"""FAQ chatbot: retrieve relevant FAQ entries, then let the LLM answer from them (RAG)."""

import logging

from app.core.config import Settings
from app.prompts import CHAT_PROMPT_TEMPLATE
from app.schemas import ChatResponse
from app.services.faq_service import FaqRetriever
from app.services.gemini_client import create_gemini_client

logger = logging.getLogger(__name__)

NO_ANSWER = (
    "I don't have information about that. Please contact customer support and they will help you."
)


class ChatService:
    def __init__(self, retriever: FaqRetriever, settings: Settings, client=None):
        self._retriever = retriever
        self._settings = settings
        self._client = client

    def answer(self, question: str) -> ChatResponse:
        entries = self._retriever.search(question)
        if not entries:
            return ChatResponse(answer=NO_ANSWER, sources=[])

        sources = [entry.question for entry in entries]
        generated = self._generate(question, entries)
        # Without an LLM (no key, or a provider error) fall back to the best FAQ answer verbatim.
        return ChatResponse(answer=generated or entries[0].answer, sources=sources)

    def _generate(self, question: str, entries) -> str | None:
        if self._settings.ocr_provider == "mock" or not self._settings.gemini_api_key:
            return None
        context = "\n\n".join(f"Q: {e.question}\nA: {e.answer}" for e in entries)
        prompt = CHAT_PROMPT_TEMPLATE.format(context=context, question=question)
        try:
            client = self._client or create_gemini_client(self._settings)
            self._client = client
            response = client.models.generate_content(
                model=self._settings.gemini_model, contents=prompt
            )
            return (response.text or "").strip() or None
        except Exception as exc:
            logger.warning("Chat generation failed, using the FAQ text instead: %s", exc)
            return None
