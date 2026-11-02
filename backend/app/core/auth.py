"""Shared-secret protection for the operator and admin endpoints.

The secret travels in the `X-Review-Key` header and is compared in constant time. Wrong keys are counted per IP:
after a few failures the IP is blocked for a while, which makes guessing the key impractical.
A real system would use proper authentication (OIDC / JWT) with individual accounts and roles instead.
"""

import hmac

from fastapi import Depends, Header, Request

from app.core.config import Settings, get_settings
from app.core.errors import ReviewDisabledError, TooManyRequestsError, UnauthorizedError
from app.core.rate_limit import client_ip


def require_review_key(
    request: Request,
    x_review_key: str | None = Header(None, description="Operator secret (REVIEW_API_KEY)."),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.review_api_key:
        raise ReviewDisabledError("Operator review is not enabled on this server.")

    failures = request.app.state.limiters.admin_failures
    ip = client_ip(request)
    wait = failures.retry_after(ip)
    if wait:
        seconds = max(1, int(wait) + 1)
        raise TooManyRequestsError(
            f"Too many wrong keys. Try again in {seconds} seconds.", retry_after_seconds=seconds
        )

    supplied = (x_review_key or "").encode("utf-8")
    if not hmac.compare_digest(supplied, settings.review_api_key.encode("utf-8")):
        failures.record(ip)
        raise UnauthorizedError("Missing or invalid operator key.")
    failures.clear(ip)
