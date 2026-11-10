"""Application factory and the cross-cutting behaviour (P1-02).

Everything that applies to every request lives here: the request id, the envelope handlers, and the
health check. Routers only receive a session and a user; they never build a response by hand.

The request id is generated here and echoed by `envelope.ok`, so a caller reporting a problem can hand
over the id on screen and the log line is one search away.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import envelope
from app.config import get_settings
from app.db import PROJECT_ROOT, engine_from_dsn, resolve_dsn
from app.envelope import (
    BAD_PARAM,
    INTERNAL,
    MISSING_PARAM,
    NOT_FOUND,
    STATUS,
    UNAUTHENTICATED,
    ApiError,
    request_id_ctx,
)
from app.envelope import (
    envelope as build,
)
from app.routers import (
    auth,
    capture,
    datasets,
    detect,
    experiments,
    hard_samples,
    models,
    reports,
    review,
    species,
    stats,
    system,
    tasks,
    users,
)
from app.worker import Worker

log = logging.getLogger("aquavision")

ROUTERS = (
    auth.router,
    users.router,
    capture.router,
    tasks.router,
    detect.router,
    experiments.router,
    review.router,
    hard_samples.router,
    datasets.router,
    stats.router,
    reports.router,
    models.router,
    species.router,
    system.router,
)


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]
) -> JSONResponse:
    """Give every request an id, put it on the context, and echo it in the header."""
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    token = request_id_ctx.set(request_id)
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-Id"] = request_id
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the detection pool with the app; stop it before the process exits."""
    worker = None
    if getattr(app.state, "worker_enabled", False):
        worker = Worker(
            app.state.session_factory,
            workers=getattr(app.state, "max_concurrency", 1),
            poll_seconds=getattr(app.state, "worker_poll_seconds", 1.0),
        )
        worker.start()
        app.state.worker = worker
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AquaVision",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    dsn = resolve_dsn(settings.db_dsn)
    if dsn.startswith("sqlite:///"):
        Path(dsn.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = engine_from_dsn(dsn)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app.state.dsn = dsn
    app.state.worker_enabled = settings.worker_enabled
    app.state.worker_poll_seconds = settings.worker_poll_seconds
    app.state.max_concurrency = settings.max_concurrency

    app.middleware("http")(request_context)

    @app.exception_handler(ApiError)
    async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=build(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def on_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"参数有误：{field}" if field else "参数有误"
        return JSONResponse(status_code=400, content=build(MISSING_PARAM, message))

    @app.exception_handler(StarletteHTTPException)
    async def on_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 401:
            return JSONResponse(status_code=401, content=build(UNAUTHENTICATED, "请先登录"))
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content=build(NOT_FOUND, "接口不存在"))
        return JSONResponse(status_code=exc.status_code, content=build(BAD_PARAM, str(exc.detail)))

    @app.exception_handler(Exception)
    async def on_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Never a bare 500 with a stack trace: the detail goes to the log, the code to the caller.
        log.exception("unhandled error", exc_info=exc)
        return JSONResponse(status_code=STATUS[INTERNAL], content=build(INTERNAL, "服务器内部错误"))

    @app.get("/api/health")
    def health() -> dict[str, object]:
        """Liveness and the three facts a deployer needs: database, secret, mounted routes."""
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database = "ok"
        except SQLAlchemyError as err:
            database = f"unavailable: {type(err).__name__}"

        return envelope.ok(
            {
                "status": "ok" if database == "ok" else "degraded",
                "database": database,
                # Included routers are nested, so counting `app.routes` counts wrappers.
                "routes": sum(len(router.routes) for router in ROUTERS) + 1,
                "contract_routes": 42,
                "jwt_secret_is_default": settings.jwt_secret_is_default,
            }
        )

    for router in ROUTERS:
        app.include_router(router)

    # The backend serves the pages as well as the API, so a browser has one origin for both. Without this
    # the frontend's relative `/api` calls went to whichever static server was serving the pages and came
    # back as "interface not found" - a proxy was assumed and never committed, so a newcomer needed two
    # terminals, two ports and a proxy to see a page talk to the API.
    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/templates/login.html")

    web_root = PROJECT_ROOT / "web"
    if web_root.is_dir():
        app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
    return app


app = create_app()
