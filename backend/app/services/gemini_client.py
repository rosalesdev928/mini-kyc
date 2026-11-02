"""Factory for the Gemini client. The API key always comes from the environment."""

from app.core.config import Settings
from app.core.errors import OcrNotConfiguredError


def create_gemini_client(settings: Settings):
    if not settings.gemini_api_key:
        raise OcrNotConfiguredError(
            "The AI service is not configured. Set the GEMINI_API_KEY environment variable."
        )
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
    )
