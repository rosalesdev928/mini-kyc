"""Contingency plan of the Gemini provider: retries, fallback model and time budget (no network)."""

import pytest

from app.core.config import Settings
from app.core.errors import ExtractionFailedError, OcrProviderError, OcrRateLimitedError
from app.services.ocr_service import GeminiOcrProvider

GOOD_ANSWER = (
    '{"is_identity_document": true, "is_legible": true, "document_type": "DNI",'
    ' "full_name": "Maria Fernandez", "document_number": "12345678", "confidence": 0.95}'
)


class FakeApiError(Exception):
    """Looks like the SDK's APIError: it carries the HTTP status in `.code`."""

    def __init__(self, code: int):
        super().__init__(f"{code} simulated error")
        self.code = code


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class FakeModels:
    def __init__(self, script):
        self.script = list(script)  # each item: an exception to raise or the text to return
        self.models_called: list[str] = []

    def generate_content(self, *, model, contents, config):
        self.models_called.append(model)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


class FakeClient:
    def __init__(self, script):
        self.models = FakeModels(script)


class FakeTime:
    """A clock that only moves when the provider "sleeps"."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


def provider_for(script, **settings_overrides):
    values = dict(
        gemini_api_key="test-key",
        gemini_model="primary",
        gemini_fallback_model="backup",
        gemini_max_attempts=3,
        gemini_retry_base_seconds=1.0,
        gemini_total_budget_seconds=80.0,
    )
    values.update(settings_overrides)
    fake_time = FakeTime()
    client = FakeClient(script)
    provider = GeminiOcrProvider(
        Settings(**values), client=client, sleep=fake_time.sleep, clock=fake_time.clock
    )
    return provider, client, fake_time


def run(provider):
    return provider.extract(b"fake-image-bytes", "image/png")


def test_success_on_the_first_attempt_does_not_sleep():
    provider, client, fake_time = provider_for([GOOD_ANSWER])
    assert run(provider).document_number == "12345678"
    assert client.models.models_called == ["primary"]
    assert fake_time.sleeps == []


def test_transient_errors_are_retried_with_exponential_backoff():
    provider, client, fake_time = provider_for([FakeApiError(503), FakeApiError(504), GOOD_ANSWER])
    assert run(provider).full_name == "Maria Fernandez"
    assert client.models.models_called == ["primary", "primary", "primary"]
    assert fake_time.sleeps == [1.0, 2.0]


def test_fallback_model_is_used_when_the_primary_keeps_failing():
    script = [FakeApiError(503)] * 3 + [GOOD_ANSWER]
    provider, client, fake_time = provider_for(script)
    assert run(provider).document_number == "12345678"
    assert client.models.models_called == ["primary"] * 3 + ["backup"]
    assert fake_time.sleeps == [1.0, 2.0]  # no pointless sleep after the last attempt of a model


def test_all_attempts_failing_returns_a_controlled_provider_error():
    provider, client, _ = provider_for([FakeApiError(503)] * 6)
    with pytest.raises(OcrProviderError):
        run(provider)
    assert len(client.models.models_called) == 6


def test_rate_limit_everywhere_is_reported_as_rate_limited():
    provider, _, _ = provider_for([FakeApiError(429)] * 6)
    with pytest.raises(OcrRateLimitedError):
        run(provider)


def test_non_retryable_error_fails_immediately():
    provider, client, fake_time = provider_for([FakeApiError(400), GOOD_ANSWER])
    with pytest.raises(OcrProviderError):
        run(provider)
    assert client.models.models_called == ["primary"]
    assert fake_time.sleeps == []


def test_unknown_model_goes_straight_to_the_fallback():
    provider, client, fake_time = provider_for([FakeApiError(404), GOOD_ANSWER])
    assert run(provider).document_number == "12345678"
    assert client.models.models_called == ["primary", "backup"]
    assert fake_time.sleeps == []


def test_network_errors_without_status_are_retried():
    provider, client, _ = provider_for([TimeoutError("read timed out"), GOOD_ANSWER])
    assert run(provider).document_number == "12345678"
    assert client.models.models_called == ["primary", "primary"]


def test_time_budget_stops_the_retries():
    provider, client, fake_time = provider_for(
        [FakeApiError(503)] * 6, gemini_total_budget_seconds=2.0
    )
    with pytest.raises(OcrProviderError):
        run(provider)
    assert len(client.models.models_called) == 2  # the 2nd backoff (2 s) would exceed the budget
    assert fake_time.sleeps == [1.0]


def test_without_fallback_model_only_the_primary_is_used():
    provider, client, _ = provider_for([FakeApiError(503)] * 3, gemini_fallback_model="")
    with pytest.raises(OcrProviderError):
        run(provider)
    assert client.models.models_called == ["primary"] * 3


def test_unreadable_answer_is_not_retried():
    provider, client, _ = provider_for(["this is not json", GOOD_ANSWER])
    with pytest.raises(ExtractionFailedError):
        run(provider)
    assert client.models.models_called == ["primary"]
