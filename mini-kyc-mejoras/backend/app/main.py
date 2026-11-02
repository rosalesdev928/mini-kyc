"""FastAPI application factory."""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, get_settings
from app.core.database import run_migrations
from app.core.errors import AppError
from app.core.logging_config import configure_logging, request_id_var
from app.routers import chat, health, onboarding, review

logger = logging.getLogger("mini_kyc")


def _error_response(status_code: int, code: str, message: str, details: object | None = None):
    body: dict = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.auto_migrate:
            try:
                run_migrations(settings)
            except Exception as exc:  # keep the API up; /health will report the database as down
                logger.error("Database migration failed: %s", exc)
        yield

    app = FastAPI(
        title="Mini KYC - Digital Onboarding API",
        version="1.0.0",
        description=(
            "Proof of concept of a KYC flow: upload an identity document image, extract the data with "
            "AI/OCR, and store the onboarding record through stored procedures."
        ),
        lifespan=lifespan,
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Tag the request with an id (reuses X-Request-ID if the client sends one) and log its outcome."""
        supplied = re.sub(r"[^A-Za-z0-9._-]", "", request.headers.get("x-request-id", ""))[:64]
        request_id = supplied or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            if request.url.path != "/api/v1/health":  # the uptime monitor calls it every 5 minutes
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.info(
                    "%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms
                )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        problems = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return _error_response(422, "VALIDATION_ERROR", "The request is not valid.", problems)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        logger.exception("Unexpected error: %s", exc)
        return _error_response(500, "INTERNAL_ERROR", "Something went wrong. Please try again later.")

    app.include_router(health.router)
    app.include_router(onboarding.router)
    app.include_router(review.router)
    app.include_router(chat.router)

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """In production the API also serves the built React app (single deployable service)."""
    static_dir = Path(settings.static_dir) if settings.static_dir else None
    if not static_dir or not (static_dir / "index.html").exists():
        return

    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str):
        if path.startswith("api/"):
            return _error_response(404, "NOT_FOUND", "Resource not found.")
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")


app = create_app()
