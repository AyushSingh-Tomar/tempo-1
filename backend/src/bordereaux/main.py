"""FastAPI application factory.

Run locally (from ``backend/``)::

    .\\venv\\Scripts\\python.exe -m uvicorn bordereaux.main:app --reload

Wiring (available on ``app.state`` to dependencies):
    settings, engine, session_factory, storage (StorageService), auth_provider (AuthProvider)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from bordereaux import __version__
from bordereaux.ai.service import build_llm_service
from bordereaux.api.v1 import api_router
from bordereaux.auth.dev_provider import DevAuthProvider
from bordereaux.config import Settings, get_settings
from bordereaux.core.context import RequestContext, reset_request_context, set_request_context
from bordereaux.core.database import check_database, create_engine, create_session_factory
from bordereaux.core.exceptions import ApplicationError
from bordereaux.core.utils import error_envelope, new_request_id
from bordereaux.storage.local import LocalStorageService

logger = logging.getLogger("bordereaux")

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _upgrade_database(database_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")

_HTTP_CODE_MAP = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    429: "RATE_LIMITED",
}


class RequestContextMiddleware:
    """Assigns a request id (or honours an incoming ``X-Request-ID``), exposes it
    as ``request.state.request_id`` and the ``X-Request-ID`` response header, and
    publishes request context (ip, user agent) for audit logging."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        incoming = headers.get("x-request-id", "")
        request_id = incoming if 0 < len(incoming) <= 100 and incoming.isprintable() else new_request_id()
        client = scope.get("client")
        scope.setdefault("state", {})["request_id"] = request_id
        token = set_request_context(
            RequestContext(
                request_id=request_id,
                client_ip=client[0] if client else None,
                user_agent=headers.get("user-agent"),
            )
        )

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-request-id", request_id.encode("latin-1"))]
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            reset_request_context(token)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def _app_error(request: Request, exc: ApplicationError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        if exc.status_code >= 500:
            logger.error("Application error %s: %s", exc.code, exc.message, extra={"request_id": _request_id(request)})
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.to_dict(), _request_id(request)),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")),
                "code": str(err.get("type", "invalid")).upper(),
                "message": err.get("msg", "Invalid value"),
            }
            for err in exc.errors()
        ]
        body = {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}
        return JSONResponse(status_code=400, content=error_envelope(body, _request_id(request)))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        body = {"code": code, "message": message, "details": []}
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(body, _request_id(request)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        logger.exception("Unhandled error", extra={"request_id": rid})
        body = {"code": "INTERNAL_ERROR", "message": f"An internal error occurred. Reference: {rid}", "details": []}
        return JSONResponse(status_code=500, content=error_envelope(body, rid))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    if settings.storage_backend != "local":
        raise ValueError(f"Unsupported STORAGE_BACKEND {settings.storage_backend!r} (only 'local' in iteration 1)")
    if settings.auth_provider != "dev":
        raise ValueError(f"Unsupported AUTH_PROVIDER {settings.auth_provider!r} (only 'dev' in iteration 1)")

    engine = create_engine(settings.database_url, echo=settings.database_echo)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if settings.auto_migrate and settings.is_sqlite and _ALEMBIC_INI.is_file():
            # env.py calls asyncio.run(), so migrate in a worker thread.
            await asyncio.to_thread(_upgrade_database, settings.database_url)
            logger.info("Database migrated to head")
        yield
        await engine.dispose()

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

    # State is set eagerly (not in lifespan) so ASGI test clients that skip
    # lifespan events still get a fully wired app.
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.storage = LocalStorageService(settings.storage_root)
    app.state.llm_service = build_llm_service(settings)
    app.state.auth_provider = DevAuthProvider(
        allowed_tokens=settings.dev_auth_token_list, session_factory=session_factory
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )
    app.add_middleware(RequestContextMiddleware)
    _register_exception_handlers(app)

    @app.get("/health", tags=["system"])
    async def health(request: Request) -> JSONResponse:
        db_ok = await check_database(request.app.state.engine)
        storage_ok = await request.app.state.storage.health_check()
        llm_ok = request.app.state.llm_service.is_available()
        checks: dict[str, Any] = {
            "database": "ok" if db_ok else "error",
            "storage": "ok" if storage_ok else "error",
        }
        if request.app.state.settings.llm_enabled:
            checks["llm"] = "configured" if llm_ok else "not_configured"
        healthy = db_ok and storage_ok
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "healthy" if healthy else "unhealthy", "checks": checks},
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    """Lazily build ``bordereaux.main:app`` on first access (PEP 562), so merely
    importing this module (e.g. from tests calling ``create_app``) has no side
    effects such as creating the storage directory."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
